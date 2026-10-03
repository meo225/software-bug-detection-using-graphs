"""Path helpers resolve inside this repository."""

from src.utils.paths import data_dir, repo_root, resolve_from_root


def test_repo_root_contains_project_files() -> None:
    root = repo_root()
    assert (root / "README.md").is_file()
    assert (root / "src" / "utils" / "paths.py").is_file()
    assert (root / "configs" / "data" / "diversevul.yaml").is_file()


def test_resolve_from_root_stays_inside_the_repository() -> None:
    path = resolve_from_root("data", "raw", "diversevul")
    assert path.is_relative_to(repo_root())
    assert path == data_dir("raw", "diversevul")
