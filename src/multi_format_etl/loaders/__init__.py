"""Format-specific loaders: one module per source format."""

from multi_format_etl.loaders.csv_loader import load_csv
from multi_format_etl.loaders.json_loader import load_json
from multi_format_etl.loaders.log_loader import load_logs
from multi_format_etl.loaders.xml_loader import load_xml

__all__ = ["load_csv", "load_json", "load_xml", "load_logs"]
