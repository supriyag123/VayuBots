from tools.airtable_utils import _tbl

posts = _tbl("Posts").all(
    formula="{Approval Status}='Approved'",
    max_records=1
)

caption = posts[0]['fields']['Caption']

print("Raw caption from Airtable:")
print(repr(caption))
print("\nFirst 20 chars as unicode:")
for i, char in enumerate(caption[:20]):
    print(f"{i}: {char} (U+{ord(char):04X})")
