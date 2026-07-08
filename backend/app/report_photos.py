import math
from io import BytesIO

from openpyxl.drawing.image import Image as XLImage
from openpyxl.drawing.spreadsheet_drawing import AnchorMarker, OneCellAnchor
from openpyxl.drawing.xdr import XDRPositiveSize2D
from openpyxl.utils.units import pixels_to_EMU
from PIL import Image as PILImage

BLOCK_WIDTH_PX = 658
BLOCK_HEIGHT_PX = 378


def compute_grid(count: int) -> tuple[int, int]:
    if count <= 0:
        return (0, 0)
    cols = math.ceil(math.sqrt(count))
    rows = math.ceil(count / cols)
    return (cols, rows)


def _resize_to_fit(image_bytes: bytes, max_width: int, max_height: int) -> tuple[bytes, int, int]:
    with PILImage.open(BytesIO(image_bytes)) as img:
        img = img.convert("RGB")
        ratio = min(max_width / img.width, max_height / img.height, 1.0)
        new_size = (max(1, round(img.width * ratio)), max(1, round(img.height * ratio)))
        resized = img.resize(new_size)
        buffer = BytesIO()
        resized.save(buffer, format="PNG")
        return buffer.getvalue(), new_size[0], new_size[1]


def insert_photo_grid(worksheet, anchor_row: int, photos: list[bytes]) -> None:
    if not photos:
        return

    cols, rows = compute_grid(len(photos))
    cell_width = BLOCK_WIDTH_PX // cols
    cell_height = BLOCK_HEIGHT_PX // rows

    for index, photo_bytes in enumerate(photos):
        col_index = index % cols
        row_index = index // cols
        resized_bytes, width, height = _resize_to_fit(photo_bytes, cell_width, cell_height)

        image = XLImage(BytesIO(resized_bytes))
        marker = AnchorMarker(
            col=0,
            colOff=pixels_to_EMU(col_index * cell_width),
            row=anchor_row - 1,
            rowOff=pixels_to_EMU(row_index * cell_height),
        )
        image.anchor = OneCellAnchor(
            _from=marker,
            ext=XDRPositiveSize2D(pixels_to_EMU(width), pixels_to_EMU(height)),
        )
        worksheet.add_image(image)
