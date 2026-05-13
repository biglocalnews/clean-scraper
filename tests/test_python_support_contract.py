import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent


def _read_repo_file(relative_path: str) -> str:
    return (REPO_ROOT / relative_path).read_text(encoding="utf-8")


def _active_yaml(content: str) -> str:
    return "\n".join(
        line for line in content.splitlines() if not line.lstrip().startswith("#")
    )


def test_ci_workflow_python_matrix_uses_supported_versions():
    workflow = _active_yaml(
        _read_repo_file(".github/workflows/continuous-deployment.yml")
    )

    matrix_declaration = re.search(
        r"^\s*python:\s*\[(?P<versions>[^\]]+)\]", workflow, re.MULTILINE
    )
    assert matrix_declaration is not None
    matrix_versions = re.findall(
        r'["\'](\d+\.\d+)["\']', matrix_declaration.group("versions")
    )
    assert matrix_versions == ["3.10", "3.11", "3.12"]

    assert "python-version: ${{ matrix.python }}" in workflow
    assert '"3.9"' not in workflow
    assert "'3.9'" not in workflow

    pre_commit_block = re.search(
        r"pre-commit:\n(?P<body>[\s\S]*?)\n  test-python:", workflow, re.MULTILINE
    )
    assert pre_commit_block is not None

    configured_version = re.search(
        r'python-version:\s*"(?P<version>[^"]+)"', pre_commit_block.group("body")
    )
    assert configured_version is not None
    assert configured_version.group("version") in {"3.10", "3.11", "3.12"}


def test_setup_classifiers_match_supported_python_versions():
    setup_py = _read_repo_file("setup.py")

    assert "Programming Language :: Python :: 3.8" not in setup_py
    assert "Programming Language :: Python :: 3.9" not in setup_py
    assert "Programming Language :: Python :: 3.10" in setup_py
    assert "Programming Language :: Python :: 3.11" in setup_py
    assert "Programming Language :: Python :: 3.12" in setup_py
    assert re.search(r'python_requires\s*=\s*["\']>=3\.10["\']', setup_py) is not None


def test_ci_workflow_commented_python_versions_avoid_eol():
    workflow = _read_repo_file(".github/workflows/continuous-deployment.yml")

    assert "python-version: '3.9'" not in workflow
    assert 'python-version: "3.9"' not in workflow


def test_tox_env_list_uses_supported_python_versions():
    tox_ini = _read_repo_file("tox.ini")

    assert "py39" not in tox_ini
    assert "py{310,311,312}" in tox_ini


def test_pre_commit_pyupgrade_target_matches_project_python_floor():
    pre_commit_config = _read_repo_file(".pre-commit-config.yaml")

    assert "--py310-plus" in pre_commit_config
