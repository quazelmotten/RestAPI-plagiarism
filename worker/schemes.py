from pydantic import BaseModel, field_validator


class EnginePlagiarismParams(BaseModel):
    file1: str
    file2: str
    language: str

    class Config:
        extra = "allow"


class EnginePlagiarismParamsBuilder(EnginePlagiarismParams):
    @field_validator("file1")
    def validate_file1(cls, v):
        return f"--file1 {v}"

    @field_validator("file2")
    def validate_file2(cls, v):
        return f"--file2 {v}"

    @field_validator("language")
    def validate_language(cls, v):
        return f"--language {v}"

    class Config:
        exclude_none = True
        extra = "allow"
