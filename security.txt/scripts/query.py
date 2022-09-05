from typing import Final

import csv
import pathlib
import urllib.parse

import requests
import typer
from loguru import logger
from alive_progress import alive_bar


LOG_FILE_PATH: pathlib.Path = pathlib.Path("./query.log")

SCHEMA: Final[str] = "https://"

REQUIRED_FIELDS: Final[list[str]] = ["contact"]
INTERESTING_FIELDS: Final[list[str]] = REQUIRED_FIELDS + [
    "expires",  # Technically this is required, but lots of security.txt files don't have it.
    "hiring",
    "policy",
    "acknowledgements",
]
SECURITY_DOT_TXT_PATHS: Final[list[str]] = [
    "/.well-known/security.txt",
    "/security.txt",
]


def main(
    sites_path: pathlib.Path = typer.Argument(
        ..., help="Path to CSV with the sites to check for security.txt."
    ),
    out_path: pathlib.Path = typer.Argument(
        ..., help="Path to output results of querying the sites for security.txt files."
    ),
    security_dot_txt_paths: list[str] = typer.Option(
        default=SECURITY_DOT_TXT_PATHS,
        help="Paths to check for security.txt files under each domain/URL.",
    ),
    log_file_path: pathlib.Path = typer.Option(
        default=LOG_FILE_PATH,
        help="Path to write logs to.",
    ),
) -> None:
    logger.add(log_file_path, level="TRACE")

    logger.info(f"Reading sites from {sites_path} and writing to {out_path}...")

    logger.debug(f"Getting number of rows from {sites_path}..")
    num_rows = 0
    with open(sites_path, "r") as sites_file:
        num_rows = sum(1 for _ in csv.DictReader(sites_file))
    logger.debug(f"Got {num_rows} rows from {sites_path}.")

    last_queried = 0
    if out_path.exists():
        logger.debug(f"Getting index of last-queried site from {out_path}...")
        with open(out_path, "r") as out_file:
            reader = csv.DictReader(out_file)
            for row in reader:
                last_row = row
            last_queried = int(last_row["index"]) + 1
        logger.debug(f"Got {last_queried} already-queries sites from {out_path}.")

    num_rows -= last_queried

    with open(sites_path, "r") as sites_file, open(
        out_path, "a"
    ) as out_file, alive_bar(num_rows) as bar:
        reader = csv.DictReader(sites_file)
        writer = csv.DictWriter(
            out_file, fieldnames=["index", "site"] + INTERESTING_FIELDS
        )

        if last_queried == 0:
            writer.writeheader()
        for i, row in enumerate(reader):
            if i <= last_queried:
                logger.trace("Skipping already-queried site.")
                continue

            site = SCHEMA + row["Domain"]
            logger.debug(f"Checking {site}...")

            has_securitytxt = False

            for path in security_dot_txt_paths:
                url = urllib.parse.urljoin(site, path)

                logger.trace(f"Querying {url} for security.txt...")
                try:
                    response = requests.get(url, allow_redirects=True, timeout=5)
                except Exception:
                    logger.info(
                        f"Something went wrong when connecting to {url}, skipping."
                    )
                    continue
                logger.trace(f"Successfully queried {url} for security.txt.")

                if response.status_code != 200:
                    logger.debug(
                        f"Did not get an OK response from {url}, instead got {response.reason}, skipping."
                    )
                    continue

                logger.debug("Checking if security.txt is valid...")
                if response.text.startswith("<"):
                    logger.debug("security.txt looks like an HTML file, invalid.")
                    continue

                logger.debug("Parsing fields from security.txt file...")
                fields: dict[str, list[str]] = {}
                for line in response.text.splitlines():
                    if len(line) == 0 or line.startswith("#"):
                        continue
                    try:
                        field, value = line.lower().split(": ", 1)
                    except ValueError:
                        continue
                    if field not in fields:
                        fields[field] = []
                    fields[field].append(value)
                if not all(field.lower() in fields for field in REQUIRED_FIELDS):
                    logger.debug(
                        "security.txt does not have all the required fields, invalid."
                    )
                    continue

                logger.debug(f"Found valid security.txt at {url}")
                has_securitytxt = True

                output = dict(
                    map(
                        lambda x: (x[0], " ".join(x[1])),
                        filter(lambda x: x[0] in INTERESTING_FIELDS, fields.items()),
                    )
                )
                writer.writerow({"index": i, "site": site, **output})

                break

            if has_securitytxt:
                logger.success(
                    f"Successfully checked {site}, found valid security.txt!"
                )
            else:
                logger.debug(
                    f"Successfully checked {site}, no valid security.txt found."
                )

            bar()


if __name__ == "__main__":
    typer.run(main)
