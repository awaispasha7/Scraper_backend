import os
import hashlib
import sys
from pathlib import Path

# Add shared utils
project_root = Path(__file__).resolve().parents[0]
if str(project_root) not in sys.path:
    sys.path.append(str(project_root))

from utils.address_utils import normalize_address, generate_address_hash

addresses = [
    "10212 1/2 S Malta St, Chicago, IL 60643",
    "10212 1/2 S Malta St",
    "4800 S Lake Park Ave Unit 2107, Chicago, IL 60615",
    "4800 S Lake Park Ave Unit 2107"
]

print(f"{'Original Address':<50} | {'Normalized (Python)':<50} | {'Hash (Python)':<32}")
print("-" * 140)

for addr in addresses:
    normalized = normalize_address(addr)
    addr_hash = generate_address_hash(normalized)
    print(f"{addr:<50} | {normalized:<50} | {addr_hash:<32}")
