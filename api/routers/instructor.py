"""Instructor endpoints for managing students and submissions."""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from core.student_store import get_student_repository, sanitize_student_name
from core.submission_store import get_submission_repository
from models.submissions import StudentSummary, SubmissionSummary, Submission

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/instructor", tags=["Instructor"])


class StudentListResponse(BaseModel):
    """Response for listing students."""
    
    students: list[StudentSummary]
    total_count: int


class SubmissionListResponse(BaseModel):
    """Response for listing submissions."""
    
    submissions: list[SubmissionSummary]
    total_count: int


class ResetResponse(BaseModel):
    """Response for reset operations."""
    
    deleted_count: int
    message: str


class SubmissionDetailResponse(BaseModel):
    """Detailed submission with log content."""
    
    id: str
    student_name: str
    display_name: str
    submitted_at: str
    project_name: str
    it_logs: str
    ot_logs: str
    it_log_lines: int
    ot_log_lines: int


@router.get(
    "/students",
    response_model=StudentListResponse,
    summary="List all students with active sessions",
    description="Get a list of all students who have set up logging.",
)
async def list_students() -> StudentListResponse:
    """List all students with active logging sessions."""
    student_repo = get_student_repository()
    submission_repo = get_submission_repository()
    
    # Get submission counts per student
    submission_counts = submission_repo.count_by_student()
    
    # Get student summaries with submission counts
    summaries = student_repo.list_summaries(submission_counts)
    
    return StudentListResponse(
        students=summaries,
        total_count=len(summaries),
    )


@router.get(
    "/submissions",
    response_model=SubmissionListResponse,
    summary="List all submissions",
    description="Get a list of all submissions, optionally filtered by student name.",
)
async def list_submissions(
    student_name: str | None = None,
) -> SubmissionListResponse:
    """List all submissions, optionally filtered by student."""
    submission_repo = get_submission_repository()
    
    if student_name:
        try:
            sanitized = sanitize_student_name(student_name)
            submissions = submission_repo.list_for_student(sanitized)
        except ValueError as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(e),
            )
    else:
        submissions = submission_repo.list_all()
    
    return SubmissionListResponse(
        submissions=submissions,
        total_count=len(submissions),
    )


@router.get(
    "/submissions/{student_name}/{submission_id}",
    response_model=SubmissionDetailResponse,
    summary="Get submission details",
    description="Get full details of a submission including log content.",
)
async def get_submission(
    student_name: str,
    submission_id: str,
) -> SubmissionDetailResponse:
    """Get a specific submission with full log content."""
    try:
        sanitized = sanitize_student_name(student_name)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    
    submission_repo = get_submission_repository()
    submission = submission_repo.get(sanitized, submission_id)
    
    if not submission:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Submission '{submission_id}' not found for student '{student_name}'",
        )
    
    return SubmissionDetailResponse(
        id=submission.id,
        student_name=submission.student_name,
        display_name=submission.display_name,
        submitted_at=submission.submitted_at.isoformat(),
        project_name=submission.project_name,
        it_logs=submission.it_logs,
        ot_logs=submission.ot_logs,
        it_log_lines=len(submission.it_logs.splitlines()) if submission.it_logs else 0,
        ot_log_lines=len(submission.ot_logs.splitlines()) if submission.ot_logs else 0,
    )


@router.delete(
    "/submissions/{student_name}/{submission_id}",
    response_model=ResetResponse,
    summary="Delete a specific submission",
    description="Delete a single submission by student name and submission ID.",
)
async def delete_submission(
    student_name: str,
    submission_id: str,
) -> ResetResponse:
    """Delete a specific submission."""
    try:
        sanitized = sanitize_student_name(student_name)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    
    submission_repo = get_submission_repository()
    deleted = submission_repo.delete(sanitized, submission_id)
    
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Submission '{submission_id}' not found for student '{student_name}'",
        )
    
    return ResetResponse(
        deleted_count=1,
        message=f"Deleted submission '{submission_id}' for student '{student_name}'",
    )


@router.delete(
    "/students/{student_name}",
    response_model=ResetResponse,
    summary="Delete a student session",
    description="""
Delete a student's logging session. 

Note: This only removes the session data, not the syslog collector nodes in GNS3.
Use the /logging/{student_name}/teardown endpoint to remove the nodes as well.
Submissions are NOT deleted.
""",
)
async def delete_student(student_name: str) -> ResetResponse:
    """Delete a student's session (not their submissions)."""
    try:
        sanitized = sanitize_student_name(student_name)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    
    student_repo = get_student_repository()
    deleted = student_repo.delete(sanitized)
    
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No active session found for student '{student_name}'",
        )
    
    return ResetResponse(
        deleted_count=1,
        message=f"Deleted session for student '{student_name}'",
    )


@router.delete(
    "/reset/submissions",
    response_model=ResetResponse,
    summary="Clear all submissions",
    description="Delete all submissions for all students. Use with caution!",
)
async def reset_submissions() -> ResetResponse:
    """Delete all submissions."""
    submission_repo = get_submission_repository()
    count = submission_repo.clear_all()
    
    return ResetResponse(
        deleted_count=count,
        message=f"Deleted {count} submission(s)",
    )


@router.delete(
    "/reset/students",
    response_model=ResetResponse,
    summary="Clear all student sessions",
    description="""
Delete all student sessions.

Note: This only removes session data, not the syslog collector nodes in GNS3.
Submissions are NOT deleted.
""",
)
async def reset_students() -> ResetResponse:
    """Delete all student sessions."""
    student_repo = get_student_repository()
    count = student_repo.clear_all()
    
    return ResetResponse(
        deleted_count=count,
        message=f"Deleted {count} student session(s)",
    )


@router.delete(
    "/reset/all",
    response_model=ResetResponse,
    summary="Clear all data",
    description="""
Delete all student sessions AND all submissions.

Note: This does not remove syslog collector nodes from GNS3.
Use with extreme caution!
""",
)
async def reset_all() -> ResetResponse:
    """Delete all students and submissions."""
    student_repo = get_student_repository()
    submission_repo = get_submission_repository()
    
    submissions_deleted = submission_repo.clear_all()
    students_deleted = student_repo.clear_all()
    
    total = submissions_deleted + students_deleted
    
    return ResetResponse(
        deleted_count=total,
        message=f"Deleted {students_deleted} student session(s) and {submissions_deleted} submission(s)",
    )
