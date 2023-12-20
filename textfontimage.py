from typing import Literal, Optional
import requests
from PIL import Image, ImageDraw, ImageFont
import numpy as np
import cv2
import os
from invokeai.app.services.image_records.image_records_common import (
    ImageCategory,
    ResourceOrigin,
)
from invokeai.app.invocations.baseinvocation import (
    BaseInvocation,
    InvocationContext,
    invocation,
    InputField,
    WithMetadata,
)
from invokeai.app.invocations.primitives import ImageField, ImageOutput

cache_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "font_cache")

os.makedirs(cache_dir, exist_ok=True)


def list_local_fonts() -> list:
    if not os.path.exists(cache_dir):
        return []
    fonts = [f for f in os.listdir(cache_dir) if f.lower().endswith((".ttf", ".otf"))]
    return sorted(fonts, key=lambda x: x.lower())


available_fonts = list_local_fonts()

if available_fonts:
    fonts_str = ", ".join([repr(f) for f in available_fonts])
    FontLiteral = eval(f'Literal["None", {fonts_str}]')
else:
    FontLiteral = Literal["None"]


@invocation(
    "Text_Font_to_Image",
    title="Text Font to Image",
    tags=["text", "mask", "font"],
    category="image",
    version="1.3.5",
    use_cache=False,
)
class TextfontimageInvocation(BaseInvocation, WithMetadata):
    """Turn Text into an image"""

    text_input: str = InputField(
        default="Invoke AI", description="The text from which to generate an image"
    )
    text_input_second_row: Optional[str] = InputField(
        description="The second row of text to add below the first text"
    )
    second_row_font_size: Optional[int] = InputField(
        default=35, description="Font size for the second row of text (optional)"
    )
    font_url: Optional[str] = InputField(
        default="https://candyfonts.com/wp-data/2019/04/06/51421/ARIALBD.TTF",
        description="URL address of the font file to download",
    )
    local_font_path: Optional[str] = InputField(
        description="Local font file path (overrides font_url)"
    )
    local_font: FontLiteral = InputField(
        default=None,
        description="Name of the local font file to use from the font_cache folder",
    )
    image_width: int = InputField(default=1024, description="Width of the output image")
    image_height: int = InputField(
        default=512, description="Height of the output image"
    )
    padding: int = InputField(
        default=100, description="Padding around the text in pixels"
    )
    row_gap: int = InputField(
        default=50, description="Gap between the two rows of text in pixels"
    )

    def download_font(self, font_url: str) -> str:
        font_filename = font_url.split("/")[-1]
        font_path = os.path.join(cache_dir, font_filename)

        if not os.path.exists(cache_dir):
            os.makedirs(cache_dir)

        if not os.path.isfile(font_path):
            print("\033[1;31mFont not found in cache, downloading...\033[0m")
            response = requests.get(font_url)
            with open(font_path, "wb") as f:
                f.write(response.content)
        else:
            print("\033[1;32mFont found in cache, using cached version.\033[0m")

        return font_path

    def find_font_size(
        self,
        font_path: str,
        text: str,
        image_width: int,
        image_height: int,
        padding: int,
    ) -> int:
        max_font_size = 1000
        font_size = max_font_size

        try:
            font = ImageFont.truetype(font_path, font_size)
        except OSError as e:
            raise ValueError(f"Error opening font file: {str(e)}")

        text_bbox = font.getbbox(text)
        text_width, text_height = (
            text_bbox[2] - text_bbox[0],
            text_bbox[3] - text_bbox[1],
        )

        while (text_width + 2 * padding > image_width) or (
            text_height + 2 * padding > image_height
        ):
            font_size -= 1
            try:
                font = ImageFont.truetype(font_path, font_size)
            except OSError as e:
                raise ValueError(f"Error opening font file: {str(e)}")

            text_bbox = font.getbbox(text)
            text_width, text_height = (
                text_bbox[2] - text_bbox[0],
                text_bbox[3] - text_bbox[1],
            )

        return font_size

    def text_to_image(
        self,
        text: str,
        text_second_row: Optional[str],
        font_path: str,
        font_size: int,
        second_row_font_size: Optional[int],
        image_width: int,
        image_height: int,
        padding: int,
        row_gap: int,
    ) -> Image:
        font = ImageFont.truetype(font_path, font_size)

        text_bbox = font.getbbox(text)
        text_width, text_height = (
            text_bbox[2] - text_bbox[0],
            text_bbox[3] - text_bbox[1],
        )

        if text_second_row and second_row_font_size is not None:
            second_row_font = ImageFont.truetype(font_path, second_row_font_size)

            text_bbox_2 = second_row_font.getbbox(text_second_row)
            text_width_2, text_height_2 = (
                text_bbox_2[2] - text_bbox_2[0],
                text_bbox_2[3] - text_bbox_2[1],
            )

            total_text_height = text_height + text_height_2 + row_gap
            text_image_width = max(text_width, text_width_2) + 2 * padding
            text_image_height = max(total_text_height + 2 * padding, image_height)

        else:
            text_image_width = text_width + 2 * padding
            text_image_height = text_height + 2 * padding
            total_text_height = text_height

        text_image = Image.new("RGB", (text_image_width, text_image_height), (0, 0, 0))
        draw = ImageDraw.Draw(text_image)

        x = (text_image_width - text_width) // 2
        y = (text_image_height - total_text_height) // 2

        draw.text((x, y - text_bbox[1]), text, fill=(255, 255, 255), font=font)

        if text_second_row and second_row_font_size is not None:
            x = (text_image_width - text_width_2) // 2
            y += text_height + row_gap
            draw.text(
                (x, y - text_bbox_2[1]),
                text_second_row,
                fill=(255, 255, 255),
                font=second_row_font,
            )

        image = Image.new("RGB", (image_width, image_height), (0, 0, 0))

        x = (image_width - text_image_width) // 2
        y = (image_height - text_image_height) // 2

        image.paste(text_image, (x, y))

        return image

    def invoke(self, context: InvocationContext) -> ImageOutput:
        if not self.text_input:
            raise ValueError("Text input is required.")
        if self.local_font and self.local_font != "None":
            font_path = os.path.join("font_cache", self.local_font)
        elif self.local_font_path:
            font_path = self.local_font_path
        else:
            font_path = self.download_font(self.font_url)

        if not os.path.isfile(font_path):
            print(
                "\033[1;31mFont file not found. Please check the font file path.\033[0m"
            )
            return

        font_size = self.find_font_size(
            font_path,
            self.text_input,
            self.image_width,
            self.image_height,
            self.padding,
        )

        second_row_font_size = self.second_row_font_size

        if second_row_font_size is None:
            second_row_font_size = font_size

        text_image = self.text_to_image(
            self.text_input,
            self.text_input_second_row,
            font_path,
            font_size,
            second_row_font_size,
            self.image_width,
            self.image_height,
            self.padding,
            self.row_gap,
        )

        cv_mask = cv2.cvtColor(np.array(text_image), cv2.COLOR_RGB2GRAY)

        pil_mask = Image.fromarray(cv_mask)

        image_dto = context.services.images.create(
            image=pil_mask,
            image_origin=ResourceOrigin.INTERNAL,
            image_category=ImageCategory.GENERAL,
            node_id=self.id,
            session_id=context.graph_execution_state_id,
            is_intermediate=self.is_intermediate,
            metadata=self.metadata,
        )

        return ImageOutput(
            image=ImageField(image_name=image_dto.image_name),
            width=image_dto.width,
            height=image_dto.height,
        )
