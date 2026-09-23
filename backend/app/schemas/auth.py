from pydantic import AnyHttpUrl, BaseModel, ConfigDict, Field


class GitHubIdentity(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: int = Field(gt=0)
    login: str = Field(min_length=1, max_length=100)
    name: str | None = Field(default=None, max_length=255)
    avatar_url: AnyHttpUrl | None = None
    email: str | None = Field(default=None, max_length=320)


class CurrentUserResponse(BaseModel):
    model_config = ConfigDict(
        from_attributes=True,
        alias_generator=lambda name: "".join(
            word if index == 0 else word.capitalize() for index, word in enumerate(name.split("_"))
        ),
        populate_by_name=True,
    )

    id: str
    github_login: str
    display_name: str | None
    avatar_url: str | None
    is_admin: bool
