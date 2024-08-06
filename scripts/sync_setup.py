import json
import re


def parse_pipfile_lock(pipfile_lock_path):
    with open(pipfile_lock_path) as file:
        data = json.load(file)
    dependencies = {}
    for dep, details in data.get("default", {}).items():
        dependencies[dep] = details.get("version", "")
    return dependencies


def update_setup_py(setup_py_path, dependencies):
    with open(setup_py_path) as file:
        setup_py_content = file.read()

    # Find the install_requires section
    install_requires_pattern = re.compile(r"install_requires=\[(.*?)\]", re.DOTALL)
    match = install_requires_pattern.search(setup_py_content)
    if match:
        install_requires_content = match.group(1)
        new_install_requires = ",\n    ".join(
            [f"'{dep}{version}'" for dep, version in dependencies.items()]
        )
        setup_py_content = setup_py_content.replace(
            install_requires_content, new_install_requires
        )

    with open(setup_py_path, "w") as file:
        file.write(setup_py_content)


def main():
    pipfile_lock_path = "Pipfile.lock"
    setup_py_path = "setup.py"
    dependencies = parse_pipfile_lock(pipfile_lock_path)
    update_setup_py(setup_py_path, dependencies)


if __name__ == "__main__":
    main()
