"""
Endpoint extractor — heuristically identifies what a repository exposes.
Analyzes file tree paths and selected file contents for signals.
"""
from __future__ import annotations

import re
from typing import Any, Optional
from ..models.module import Endpoint, EndpointType


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _paths(tree: list[dict]) -> list[str]:
    return [item["path"] for item in tree if item.get("type") == "blob"]


def _has_file(tree: list[dict], *names: str) -> bool:
    paths = _paths(tree)
    name_set = {n.lower() for n in names}
    return any(p.lower().split("/")[-1] in name_set for p in paths)


def _files_matching(tree: list[dict], pattern: str) -> list[str]:
    regex = re.compile(pattern, re.IGNORECASE)
    return [item["path"] for item in tree if item.get("type") == "blob"
            and regex.search(item["path"])]


def _content_contains(content: Optional[str], *patterns: str) -> bool:
    if not content:
        return False
    for p in patterns:
        if re.search(p, content, re.IGNORECASE | re.MULTILINE):
            return True
    return False


# ---------------------------------------------------------------------------
# Individual detectors
# ---------------------------------------------------------------------------

def detect_rest_api(
    tree: list[dict],
    file_contents: dict[str, str],
    repo_data: dict,
) -> list[Endpoint]:
    endpoints: list[Endpoint] = []

    # FastAPI
    main_files = _files_matching(tree, r"(main|app|server|api)\.py$")
    for f in main_files:
        content = file_contents.get(f, "")
        if _content_contains(content, r"FastAPI\s*\(", r"from fastapi", r"import fastapi"):
            endpoints.append(Endpoint(
                name="FastAPI REST API",
                type=EndpointType.REST_API,
                description="Exposes HTTP endpoints via FastAPI. Auto-generates /docs (Swagger UI) "
                            "and /openapi.json.",
                details={"framework": "FastAPI", "entry_file": f},
                is_output=True,
            ))
            break

    # Flask
    for f in main_files:
        content = file_contents.get(f, "")
        if _content_contains(content, r"Flask\s*\(", r"from flask", r"import flask"):
            endpoints.append(Endpoint(
                name="Flask REST API",
                type=EndpointType.REST_API,
                description="Exposes HTTP routes via Flask.",
                details={"framework": "Flask", "entry_file": f},
                is_output=True,
            ))
            break

    # Django
    if _has_file(tree, "manage.py"):
        manage_content = file_contents.get("manage.py", "")
        if _content_contains(manage_content, r"DJANGO_SETTINGS_MODULE", r"django"):
            endpoints.append(Endpoint(
                name="Django Web Application",
                type=EndpointType.REST_API,
                description="Django project exposing HTTP views and REST endpoints.",
                details={"framework": "Django"},
                is_output=True,
            ))

    # Express / Node
    pkg_json = file_contents.get("package.json", "")
    if _content_contains(pkg_json, r'"express"', r'"koa"', r'"fastify"', r'"hapi"'):
        endpoints.append(Endpoint(
            name="Node.js HTTP Server",
            type=EndpointType.REST_API,
            description="Node.js backend exposing HTTP endpoints.",
            details={"framework": "Express/Koa/Fastify"},
            is_output=True,
        ))

    # OpenAPI / Swagger spec present
    openapi_files = _files_matching(tree, r"(openapi|swagger)\.(json|ya?ml)$")
    if openapi_files:
        endpoints.append(Endpoint(
            name="OpenAPI Specification",
            type=EndpointType.REST_API,
            description=f"Machine-readable API specification: {openapi_files[0]}",
            details={"spec_file": openapi_files[0]},
            is_output=True,
        ))

    return endpoints


def detect_cli(
    tree: list[dict],
    file_contents: dict[str, str],
    repo_data: dict,
) -> list[Endpoint]:
    endpoints: list[Endpoint] = []

    pyproject = file_contents.get("pyproject.toml", "")
    setup_py = file_contents.get("setup.py", "")
    setup_cfg = file_contents.get("setup.cfg", "")

    # pyproject.toml [project.scripts]
    match = re.search(r"\[project\.scripts\]([^\[]+)", pyproject)
    if match:
        block = match.group(1)
        scripts = re.findall(r'([\w.-]+)\s*=\s*["\']([^"\']+)["\']', block)
        for cmd, entry in scripts:
            endpoints.append(Endpoint(
                name=f"CLI: {cmd}",
                type=EndpointType.CLI,
                description=f"Command-line entry point '{cmd}' → {entry}",
                details={"command": cmd, "entry_point": entry},
                is_output=True,
            ))

    # setup.py console_scripts
    if _content_contains(setup_py, r"console_scripts"):
        endpoints.append(Endpoint(
            name="CLI (console_scripts)",
            type=EndpointType.CLI,
            description="Registered console_scripts entry points in setup.py.",
            details={"source": "setup.py"},
            is_output=True,
        ))

    # bin/ directory
    bin_files = _files_matching(tree, r"^bin/[^/]+$")
    for bf in bin_files[:3]:
        endpoints.append(Endpoint(
            name=f"CLI: {bf}",
            type=EndpointType.CLI,
            description=f"Executable script in bin/ directory: {bf}",
            details={"file": bf},
            is_output=True,
        ))

    # __main__.py pattern
    main_py_files = _files_matching(tree, r"__main__\.py$")
    if main_py_files:
        endpoints.append(Endpoint(
            name="Python Module (__main__)",
            type=EndpointType.CLI,
            description="Can be run with: python -m <package>",
            details={"files": main_py_files[:3]},
            is_output=True,
        ))

    # click / typer / argparse heavy usage
    for f in _files_matching(tree, r"cli\.py$|command[s]?\.py$"):
        content = file_contents.get(f, "")
        if _content_contains(content, r"import click", r"import typer", r"argparse"):
            endpoints.append(Endpoint(
                name=f"CLI script: {f.split('/')[-1]}",
                type=EndpointType.CLI,
                description=f"CLI implemented with click/typer/argparse in {f}",
                details={"file": f},
                is_output=True,
            ))

    return endpoints


def detect_library(
    tree: list[dict],
    file_contents: dict[str, str],
    repo_data: dict,
) -> list[Endpoint]:
    endpoints: list[Endpoint] = []

    pyproject = file_contents.get("pyproject.toml", "")
    setup_py = file_contents.get("setup.py", "")

    is_python_pkg = bool(
        re.search(r"\[project\]", pyproject) or
        re.search(r"setup\(", setup_py) or
        _files_matching(tree, r"(^|/)__init__\.py$")
    )

    if is_python_pkg:
        pkg_name = (
            re.search(r'name\s*=\s*["\']([^"\']+)["\']', pyproject) or
            re.search(r'name\s*=\s*["\']([^"\']+)["\']', setup_py)
        )
        name = pkg_name.group(1) if pkg_name else repo_data.get("name", "")
        endpoints.append(Endpoint(
            name=f"Python Package: {name}",
            type=EndpointType.LIBRARY,
            description=f"Installable Python package. Import with: import {name.replace('-','_')}",
            details={"install": f"pip install {name}", "package": name},
            is_output=True,
        ))

    # npm package
    pkg_json = file_contents.get("package.json", "")
    if pkg_json and '"name"' in pkg_json:
        npm_name = re.search(r'"name"\s*:\s*"([^"]+)"', pkg_json)
        if npm_name:
            endpoints.append(Endpoint(
                name=f"npm Package: {npm_name.group(1)}",
                type=EndpointType.LIBRARY,
                description=f"Installable npm package. Use: npm install {npm_name.group(1)}",
                details={"install": f"npm install {npm_name.group(1)}"},
                is_output=True,
            ))

    # Rust crate
    cargo_toml = file_contents.get("Cargo.toml", "")
    if cargo_toml:
        endpoints.append(Endpoint(
            name="Rust Crate",
            type=EndpointType.LIBRARY,
            description="Rust library available via cargo.io.",
            details={"source": "Cargo.toml"},
            is_output=True,
        ))

    return endpoints


def detect_data(
    tree: list[dict],
    file_contents: dict[str, str],
    repo_data: dict,
) -> list[Endpoint]:
    endpoints: list[Endpoint] = []

    data_exts = {
        ".csv": "CSV data file",
        ".parquet": "Parquet columnar data",
        ".hdf5": "HDF5 hierarchical data",
        ".h5": "HDF5 hierarchical data",
        ".jsonl": "JSON Lines data",
        ".tsv": "Tab-separated values",
        ".xlsx": "Excel spreadsheet",
        ".sqlite": "SQLite database",
        ".db": "Database file",
        ".arrow": "Apache Arrow data",
    }

    found_exts: set[str] = set()
    for item in tree:
        if item.get("type") != "blob":
            continue
        path = item["path"].lower()
        for ext, desc in data_exts.items():
            if path.endswith(ext) and ext not in found_exts:
                found_exts.add(ext)
                endpoints.append(Endpoint(
                    name=f"Data: {desc}",
                    type=EndpointType.DATA_FILE,
                    description=f"Repository contains {desc} files.",
                    details={"extension": ext},
                    is_output=True,
                ))

    return endpoints


def detect_data_structures(
    tree: list[dict],
    file_contents: dict[str, str],
    repo_data: dict,
) -> list[Endpoint]:
    endpoints: list[Endpoint] = []

    # Pydantic models
    for f in _files_matching(tree, r"(model[s]?|schema[s]?|type[s]?)\.py$"):
        content = file_contents.get(f, "")
        if _content_contains(content, r"BaseModel", r"dataclass", r"TypedDict"):
            endpoints.append(Endpoint(
                name="Pydantic / Dataclass Models",
                type=EndpointType.DATA_STRUCTURE,
                description=f"Reusable data model definitions in {f}",
                details={"file": f},
                is_output=True,
            ))
            break

    # Protobuf
    proto_files = _files_matching(tree, r"\.proto$")
    if proto_files:
        endpoints.append(Endpoint(
            name="Protobuf Definitions",
            type=EndpointType.DATA_STRUCTURE,
            description=f"{len(proto_files)} .proto file(s) defining serializable messages.",
            details={"files": proto_files[:5]},
            is_output=True,
        ))

    # JSON Schema
    schema_files = _files_matching(tree, r"schema\.json$|\.schema\.json$")
    if schema_files:
        endpoints.append(Endpoint(
            name="JSON Schema",
            type=EndpointType.DATA_STRUCTURE,
            description="JSON Schema definitions for data validation.",
            details={"files": schema_files[:3]},
            is_output=True,
        ))

    return endpoints


def detect_docker(
    tree: list[dict],
    file_contents: dict[str, str],
    repo_data: dict,
) -> list[Endpoint]:
    endpoints: list[Endpoint] = []

    if _has_file(tree, "Dockerfile"):
        endpoints.append(Endpoint(
            name="Docker Image",
            type=EndpointType.DOCKER,
            description="Can be built and run as a Docker container.",
            details={"dockerfile": "Dockerfile"},
            is_output=True,
        ))

    compose_files = _files_matching(tree, r"docker-compose(\.ya?ml)?$")
    if compose_files:
        endpoints.append(Endpoint(
            name="Docker Compose Stack",
            type=EndpointType.DOCKER,
            description="Multi-container application defined with Docker Compose.",
            details={"file": compose_files[0]},
            is_output=True,
        ))

    return endpoints


def detect_ml_model(
    tree: list[dict],
    file_contents: dict[str, str],
    repo_data: dict,
) -> list[Endpoint]:
    endpoints: list[Endpoint] = []

    model_exts = _files_matching(tree, r"\.(pt|pth|onnx|pkl|joblib|h5|safetensors|bin)$")
    if model_exts:
        endpoints.append(Endpoint(
            name="ML Model Weights",
            type=EndpointType.ML_MODEL,
            description=f"{len(model_exts)} model file(s) found ({', '.join(set(f.rsplit('.',1)[-1] for f in model_exts[:5]))}).",
            details={"files": model_exts[:5]},
            is_output=True,
        ))

    # Training / inference scripts
    train_scripts = _files_matching(tree, r"(train|predict|infer|inference)\.py$")
    if train_scripts:
        endpoints.append(Endpoint(
            name="ML Training / Inference Script",
            type=EndpointType.ML_MODEL,
            description=f"Scripts for training or running the model: {', '.join(train_scripts[:3])}",
            details={"scripts": train_scripts[:3]},
            is_output=True,
        ))

    # Hugging Face transformers
    for f in _files_matching(tree, r"\.py$"):
        content = file_contents.get(f, "")
        if _content_contains(content, r"from transformers", r"AutoModel", r"pipeline\("):
            endpoints.append(Endpoint(
                name="Hugging Face Model",
                type=EndpointType.ML_MODEL,
                description="Uses Hugging Face Transformers — model can be loaded via pipeline().",
                details={"detected_in": f},
                is_output=True,
            ))
            break

    return endpoints


def detect_graphql(
    tree: list[dict],
    file_contents: dict[str, str],
    repo_data: dict,
) -> list[Endpoint]:
    endpoints: list[Endpoint] = []

    schema_files = _files_matching(tree, r"\.graphql$|\.gql$|schema\.graphql$")
    if schema_files:
        endpoints.append(Endpoint(
            name="GraphQL Schema",
            type=EndpointType.GRAPHQL,
            description=f"GraphQL schema defined in {len(schema_files)} file(s).",
            details={"files": schema_files[:3]},
            is_output=True,
        ))

    for f in _files_matching(tree, r"\.py$"):
        content = file_contents.get(f, "")
        if _content_contains(content, r"graphene", r"strawberry", r"ariadne"):
            endpoints.append(Endpoint(
                name="GraphQL API (Python)",
                type=EndpointType.GRAPHQL,
                description="Python GraphQL server (graphene/strawberry/ariadne).",
                details={"file": f},
                is_output=True,
            ))
            break

    return endpoints


def detect_grpc(
    tree: list[dict],
    file_contents: dict[str, str],
    repo_data: dict,
) -> list[Endpoint]:
    endpoints: list[Endpoint] = []

    proto_with_service = []
    for f in _files_matching(tree, r"\.proto$"):
        content = file_contents.get(f, "")
        if _content_contains(content, r"service\s+\w+"):
            proto_with_service.append(f)

    if proto_with_service:
        endpoints.append(Endpoint(
            name="gRPC Service",
            type=EndpointType.GRPC,
            description=f"gRPC service definitions in {len(proto_with_service)} .proto file(s).",
            details={"files": proto_with_service[:3]},
            is_output=True,
        ))

    return endpoints


# ---------------------------------------------------------------------------
# Main extraction entry point
# ---------------------------------------------------------------------------

DETECTORS = [
    detect_rest_api,
    detect_cli,
    detect_library,
    detect_data,
    detect_data_structures,
    detect_docker,
    detect_ml_model,
    detect_graphql,
    detect_grpc,
]


def extract_endpoints(
    tree: list[dict],
    file_contents: dict[str, str],
    repo_data: dict,
) -> list[Endpoint]:
    """
    Run all detectors and return a deduplicated list of detected endpoints.
    """
    all_endpoints: list[Endpoint] = []
    seen_names: set[str] = set()

    for detector in DETECTORS:
        for ep in detector(tree, file_contents, repo_data):
            if ep.name not in seen_names:
                all_endpoints.append(ep)
                seen_names.add(ep.name)

    return all_endpoints
