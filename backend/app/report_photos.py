import math
from io import BytesIO

from openpyxl.drawing.image import Image as XLImage
from openpyxl.drawing.spreadsheet_drawing import AnchorMarker, OneCellAnchor
from openpyxl.drawing.xdr import XDRPositiveSize2D
from openpyxl.utils.units import pixels_to_EMU
from PIL import Image as PILImage

BLOCK_WIDTH_PX = 658
# 사진대지 블록 행(81/84행) 높이를 9.5cm로 줄인 데 맞춘 값 (9.5cm = 269.29pt = 359px @96dpi)
BLOCK_HEIGHT_PX = 359
# 사진이 칸에 꽉 차지 않도록 칸마다 사방으로 두는 여백
CELL_PADDING_PX = 8


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
    available_width = max(1, cell_width - 2 * CELL_PADDING_PX)
    available_height = max(1, cell_height - 2 * CELL_PADDING_PX)

    for index, photo_bytes in enumerate(photos):
        col_index = index % cols
        row_index = index // cols
        resized_bytes, width, height = _resize_to_fit(photo_bytes, available_width, available_height)

        # 칸보다 작게 리사이즈된 사진을 칸 한가운데에 배치해 사방으로 여백이 생기게 한다.
        col_offset = col_index * cell_width + (cell_width - width) // 2
        row_offset = row_index * cell_height + (cell_height - height) // 2

        image = XLImage(BytesIO(resized_bytes))
        marker = AnchorMarker(
            col=0,
            colOff=pixels_to_EMU(col_offset),
            row=anchor_row - 1,
            rowOff=pixels_to_EMU(row_offset),
        )
        image.anchor = OneCellAnchor(
            _from=marker,
            ext=XDRPositiveSize2D(pixels_to_EMU(width), pixels_to_EMU(height)),
        )
        worksheet.add_image(image)
