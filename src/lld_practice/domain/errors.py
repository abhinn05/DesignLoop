class DomainError(Exception):
    """A rule the practice flow refused to break."""

    def __init__(
        self,
        message: str,
        *,
        status_code: int = 400,
        errors: list[str] | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.errors = errors or []


class SubmissionValidationError(DomainError):
    def __init__(self, errors: list[str]) -> None:
        super().__init__(
            "The submission is not ready to evaluate.",
            status_code=422,
            errors=errors,
        )
