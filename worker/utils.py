from schemes import EnginePlagiarismParamsBuilder


def create_engines_params(params: dict, engine: str) -> list[str]:
    if engine == "plagiarism":
        params = EnginePlagiarismParamsBuilder.model_validate(params)

    params = params.model_dump(exclude_none=True)
    params_list = [params[key] for key in params.keys()]
    command = ["python3", f"./engines/engine_{engine}/start.py"]
    for param in params_list:
        command.extend(param.split(" "))
    return command
