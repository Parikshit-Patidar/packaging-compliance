import sys, os
sys.path.insert(0, os.path.dirname(__file__))
from ocr_service import (
    create_synthetic_package_image,
    run_local_windows_ocr,
    parse_statutory_declarations_from_text,
    locate_declaration_bounding_boxes,
    draw_statutory_spatial_overlay
)

img = create_synthetic_package_image('compliant_biscuit')
text, lines = run_local_windows_ocr(img)
dec = parse_statutory_declarations_from_text(text)
boxes = locate_declaration_bounding_boxes(dec, lines, img.size)

print("Extracted boxes count:", len(boxes))
for b in boxes:
    # safe print without unicode encoding issues
    clean_label = b['label'].encode('ascii', errors='replace').decode('ascii')
    print(f"  [{b['category']}] {clean_label} -> box={b['box']}, status={b['status']}")

annotated = draw_statutory_spatial_overlay(img, boxes, numeral_height_mm=4.0)
print("Annotated image size:", annotated.size)
print("SUCCESS!")
