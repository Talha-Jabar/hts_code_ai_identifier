# app/api/classify_router.py
from fastapi import APIRouter, HTTPException, Depends # type: ignore
from app.schemas import (
    ClassifyRequest,
    ClassifyResponseExact,
    ClassifyResponseSession,
    QuestionOut,
    OptionOut,
    AnswerRequest,
    ResultResponse,
    CandidateSummary,
)
from app.session_store import session_store
from app.services.query_service import QueryService
from pathlib import Path
from typing import Union, Optional
from uuid import uuid4

router = APIRouter(prefix="/api/classify", tags=["classify"])

# Dependency injection factory - ensures a singleton QueryService on startup
_query_service_singleton: Optional[QueryService] = None


def get_query_service() -> QueryService:
    global _query_service_singleton
    if _query_service_singleton is None:
        # Look for processed CSV in environment or default path
        default = Path.cwd() / "data" / "processed" / "hts_processed.csv"
        if not default.exists():
            raise HTTPException(
                status_code=503,
                detail=f"Processed HTS CSV not found at {default}. Run pipeline first.",
            )
        _query_service_singleton = QueryService(default)
    return _query_service_singleton


@router.post(
    "/start", response_model=Union[ClassifyResponseExact, ClassifyResponseSession]
)
def start_classification(
    req: ClassifyRequest, query_svc: QueryService = Depends(get_query_service)
):
    q = req.query.strip()
    clean = q.replace(".", "").strip()

    # Exact 10-digit match
    if clean.isdigit() and len(clean) == 10:
        results = query_svc.qa_agent.query_exact_hts(q, k=5)
        if results:
            return ClassifyResponseExact(type="exact", result=results[0]["payload"])
        else:
            # No exact match -> fallthrough to prefix/description search
            pass

    # Partial prefix
    if clean.isdigit() and len(clean) in [4, 6]:
        candidates = query_svc.qa_agent.get_candidates_by_prefix(clean)
        if candidates.empty:
            raise HTTPException(
                status_code=404, detail=f"No HTS codes found starting with '{clean}'"
            )

        session_id, indices = query_svc.build_session_from_candidates(candidates)
        session_store.create_session(session_id, indices, q)

        # try to generate first question
        question = query_svc.make_question_for_indices(indices)
        first_q = None
        if question:
            opts = [
                OptionOut(
                    label=o["label"],
                    filter_value=o.get("filter_value"),
                    expected_count=o.get("expected_count", 0),
                )
                for o in question["options"]
            ]
            first_q = QuestionOut(
                question_id=question["id"],
                question=question["question"],
                spec_column=question["spec_column"],
                options=opts,
            )
            session_store.update(session_id, current_question=question)

        return ClassifyResponseSession(
            type="session",
            session_id=session_id,
            candidates_count=len(indices),
            first_question=first_q,
        )

    # Otherwise, search by product description using vectorstore
    candidates = query_svc.qa_agent.get_candidates_by_product(q, k=200)
    if candidates.empty:
        raise HTTPException(
            status_code=404, detail="No matching products found. Try different keywords."
        )

    session_id, indices = query_svc.build_session_from_candidates(candidates)
    session_store.create_session(session_id, indices, q)
    question = query_svc.make_question_for_indices(indices)
    first_q = None
    if question:
        opts = [
            OptionOut(
                label=o["label"],
                filter_value=o.get("filter_value"),
                expected_count=o.get("expected_count", 0),
            )
            for o in question["options"]
        ]
        first_q = QuestionOut(
            question_id=question["id"],
            question=question["question"],
            spec_column=question["spec_column"],
            options=opts,
        )
        session_store.update(session_id, current_question=question)

    return ClassifyResponseSession(
        type="session", session_id=session_id, candidates_count=len(indices), first_question=first_q
    )


@router.get("/question", response_model=QuestionOut)
def get_current_question(session_id: str, query_svc: QueryService = Depends(get_query_service)):
    s = session_store.get(session_id)
    if s is None:
        raise HTTPException(status_code=404, detail="Session not found")

    # Ensure current_question exists
    if s.current_question is None:
        q = query_svc.make_question_for_indices(s.candidate_indices)
        if q is None:
            raise HTTPException(
                status_code=404, detail="No question could be generated for current candidates"
            )
        session_store.update(session_id, current_question=q)

    # refresh and re-check to narrow the Optional type
    s = session_store.get(session_id)
    if s is None or s.current_question is None:
        raise HTTPException(status_code=500, detail="Failed to retrieve question after update")

    question = s.current_question
    # explicit runtime check for analyzer
    if not isinstance(question, dict):
        raise HTTPException(status_code=500, detail="Question has unexpected structure")

    opts = [
        OptionOut(
            label=o["label"],
            filter_value=o.get("filter_value"),
            expected_count=o.get("expected_count", 0),
        )
        for o in question["options"]
    ]
    return QuestionOut(
        question_id=question["id"],
        question=question["question"],
        spec_column=question["spec_column"],
        options=opts,
    )


@router.post("/answer", response_model=ResultResponse)
def post_answer(req: AnswerRequest, query_svc: QueryService = Depends(get_query_service)):
    s = session_store.get(req.session_id)
    if s is None:
        raise HTTPException(status_code=404, detail="Session not found")

    question = s.current_question
    if question is None:
        raise HTTPException(status_code=400, detail="No active question on this session")

    # runtime check + narrow type for analyzer
    if not isinstance(question, dict):
        raise HTTPException(status_code=500, detail="Question has unexpected structure")

    # resolve selected option
    selected_option = None
    if req.selected_filter_value is not None:
        # build an option dict compatible with QueryAgent.filter_candidates_by_answer
        selected_option = {"filter_value": req.selected_filter_value}
    elif req.selected_label is not None:
        for o in question["options"]:
            if o["label"] == req.selected_label:
                selected_option = o
                break
    else:
        raise HTTPException(
            status_code=400, detail="Provide selected_label or selected_filter_value"
        )

    if selected_option is None:
        raise HTTPException(status_code=400, detail="Selected option not found")

    # apply filter
    candidates_df = query_svc.get_candidates_df(s.candidate_indices)
    filtered = query_svc.qa_agent.filter_candidates_by_answer(candidates_df, question, selected_option)
    new_indices = list(filtered.index)

    # update session atomically-ish
    # build readable history entry (safe guard when selected_option may not have 'label')
    answer_label = (
        selected_option.get("label") if isinstance(selected_option, dict) and "label" in selected_option else str(selected_option)
    )
    session_store.update(
        req.session_id,
        candidate_indices=new_indices,
        question_history=s.question_history + [{"question": question["question"], "answer": answer_label}],
    )
    # clear current question
    session_store.update(req.session_id, current_question=None)

    # If only one - finalize
    if len(new_indices) == 1:
        session_store.update(req.session_id, final_result_index=new_indices[0])
        final_payload = query_svc.details_for_index(new_indices[0])
        return ResultResponse(final=final_payload, candidates_preview=None)

    # else generate next question or return top candidates preview
    next_q = query_svc.make_question_for_indices(new_indices)
    if next_q:
        session_store.update(req.session_id, current_question=next_q)
        # return a small preview of candidates so frontend can show some context along with the new question
        preview_df = query_svc.get_candidates_df(new_indices).head(5)
        preview = [
            CandidateSummary(
                hts_number=row["HTS Number"],
                description=row.get("Description", ""),
                specifications=" > ".join([str(row.get(c, "")) for c in query_svc.qa_agent.spec_cols if row.get(c, "")]),
                unit_of_quantity=row.get("Unit_of_Quantity", ""),
            )
            for _, row in preview_df.iterrows()
        ]
        return ResultResponse(final=None, candidates_preview=preview)

    # If no next question, return top 5 candidates so frontend can show them
    preview_rows = query_svc.get_candidates_df(new_indices).head(5)
    preview = [
        CandidateSummary(
            hts_number=row["HTS Number"],
            description=row.get("Description", ""),
            specifications=" > ".join([str(row.get(c, "")) for c in query_svc.qa_agent.spec_cols if row.get(c, "")]),
            unit_of_quantity=row.get("Unit_of_Quantity", ""),
        )
        for _, row in preview_rows.iterrows()
    ]
    return ResultResponse(final=None, candidates_preview=preview)


@router.get("/result", response_model=ResultResponse)
def get_result(session_id: str, query_svc: QueryService = Depends(get_query_service)):
    s = session_store.get(session_id)
    if s is None:
        raise HTTPException(status_code=404, detail="Session not found")
    if s.final_result_index is not None:
        payload = query_svc.details_for_index(s.final_result_index)
        return ResultResponse(final=payload, candidates_preview=None)
    # else preview top 10
    df = query_svc.get_candidates_df(s.candidate_indices)
    preview = [
        CandidateSummary(
            hts_number=row["HTS Number"],
            description=row.get("Description", ""),
            specifications=" > ".join([str(row.get(c, "")) for c in query_svc.qa_agent.spec_cols if row.get(c, "")]),
            unit_of_quantity=row.get("Unit_of_Quantity", ""),
        )
        for _, row in df.head(10).iterrows()
    ]
    return ResultResponse(final=None, candidates_preview=preview)
