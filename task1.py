
import json
import urllib.request
import urllib.error
from urllib.parse import quote

from packaging.requirements import Requirement
from packaging.specifiers import SpecifierSet
from packaging.version import Version


PYTHON_VERSION = Version("3.11")


def get_release_info(package, version):
    """Fetch exact release information from PyPI."""

    url = (
        f"https://pypi.org/pypi/"
        f"{quote(package, safe='')}/{quote(version, safe='')}/json"
    )

    try:
        with urllib.request.urlopen(url, timeout=15) as response:
            data = json.load(response)

        return data["info"].get("requires_python"), None

    except urllib.error.HTTPError as error:
        if error.code == 404:
            return None, "not_found"

        return None, f"HTTP error {error.code}"

    except (urllib.error.URLError, TimeoutError) as error:
        return None, f"Network error: {error}"

    except (json.JSONDecodeError, KeyError) as error:
        return None, f"Invalid PyPI response: {error}"


def get_minimum_python(requires_python):
    """Find the highest lower bound in Requires-Python."""

    specifiers = SpecifierSet(requires_python)
    lower_bounds = []

    for spec in specifiers:
        if spec.operator in (">=", ">", "~="):
            lower_bounds.append(Version(spec.version))

        elif spec.operator == "==" and "*" not in spec.version:
            lower_bounds.append(Version(spec.version))

    if not lower_bounds:
        return None

    return max(lower_bounds)


def check_requirements():

    # Take dependencies directly from terminal.
    print("Enter dependencies (one per line).")
    print("Type END when you have finished:\n")

    lines = []

    while True:
        line = input()

        if line.strip().upper() == "END":
            break

        lines.append(line)

    not_found = []
    incompatible = []
    network_errors = []
    invalid_lines = []

    highest_requirement = None

    for line_number, line in enumerate(lines, start=1):

        line = line.strip()

        # Ignore blank lines and comments.
        if not line or line.startswith("#"):
            continue

        try:
            requirement = Requirement(line)

            package = requirement.name

            # Extract exact version pin.
            pins = [
                spec for spec in requirement.specifier
                if spec.operator == "=="
                and "*" not in spec.version
            ]

            if len(pins) != 1:
                raise ValueError("Expected an exact == version pin")

            version = pins[0].version

        except Exception as error:
            invalid_lines.append(
                (line_number, line, str(error))
            )
            continue

        requires_python, error = get_release_info(package, version)

        # Package or exact release does not exist.
        if error == "not_found":
            not_found.append(f"{package}=={version}")
            continue

        # Network/API errors.
        if error:
            network_errors.append(
                f"{package}=={version}: {error}"
            )
            continue

        # Missing Requires-Python means compatible.
        if not requires_python:
            continue

        try:
            specifiers = SpecifierSet(requires_python)

            # Check Python 3.11 compatibility.
            if not specifiers.contains(
                PYTHON_VERSION, prereleases=True
            ):
                incompatible.append(
                    f"{package}=={version} "
                    f"(Requires-Python: {requires_python})"
                )

            # Find the highest minimum Python requirement.
            minimum = get_minimum_python(requires_python)

            if minimum is not None:
                if (
                    highest_requirement is None
                    or minimum > highest_requirement[0]
                ):
                    highest_requirement = (
                        minimum,
                        package,
                        version
                    )

        except Exception as error:
            invalid_lines.append(
                (line_number, line,
                 f"Invalid Requires-Python: {error}")
            )

    # Display report.
    print("\n========== PyPI DEPENDENCY REPORT ==========\n")

    print(f"Dependencies checked: {len(lines)}")

    print(f"Not found on PyPI: {len(not_found)}")
    print(f"Incompatible with Python 3.11: {len(incompatible)}")


    print("\nHighest requirement:")

    if highest_requirement:
        minimum, package, version = highest_requirement

        print(
            f"  {package}=={version}(>={minimum})"
        )
    else:
        print("  No minimum Python requirement found.")

    if invalid_lines:
        print("\nInvalid requirements:")

        for number, line, reason in invalid_lines:
            print(f"  Line {number}: {line} ({reason})")

    if network_errors:
        print("\nCould not check (network/API errors):")

        for item in network_errors:
            print("  -", item)

    print("\n============================================")


if __name__ == "__main__":
    check_requirements()
