# DDInter source data

The application loads the original DDInter category files
`ddinter_downloads_code_*.csv` from this directory by default. Run the
loader from the project root with `python -m scripts.load_ddinter`.

The loader does not use synthetic demo data and reports an error if the
source CSV files are missing. See `docs/ddinter.md` for the verified CSV
schema and source limitations.
