from typing import Optional, Literal
import os
import requests
from PIL import Image, ImageDraw, ImageFont
from invokeai.app.models.image import ImageCategory, ResourceOrigin
from invokeai.app.invocations.baseinvocation import (
    BaseInvocation,
    InvocationContext,
    invocation,
    InputField,
)
from invokeai.app.invocations.primitives import ImageField, ImageOutput


def list_local_fonts() -> list:
    cache_dir = "font_cache"
    if not os.path.exists(cache_dir):
        return []
    fonts = [f for f in os.listdir(cache_dir) if f.lower().endswith(('.ttf', '.otf'))]
    return sorted(fonts, key=lambda x: x.lower())

available_fonts = list_local_fonts()

if available_fonts:
    fonts_str = ", ".join([repr(f) for f in available_fonts])
    FontLiteral = eval(f'Literal["None", {fonts_str}]')
else:
    FontLiteral = Literal["None"]


@invocation(
    "Advanced_Text_Font_to_Image",
    title="Advanced Text Font to Image",
    tags=["text", "overlay", "font"],
    category="image",
    version="1.2.0",
)
class AdvancedTextFontImageInvocation(BaseInvocation):
    """Overlay Text onto an image or blank canvas."""

    text_input: str = InputField(default="Invoke AI", description="The text from which to generate an image")
    text_input_second_row: Optional[str] = InputField(description="The second row of text to add below the first text")
    font_url: Optional[str] = InputField(
        default="https://candyfonts.com/wp-data/2019/04/06/51421/ARIALBD.TTF",
        description="URL address of the font file to download",
    )
    local_font_path: Optional[str] = InputField(description="Local font file path (overrides font_url)")
    local_font: Optional[FontLiteral] = InputField(
        default=None, description="Name of the local font file to use from the font_cache folder"
    )
    image_width: int = InputField(default=1024, description="Width of the output image")
    image_height: int = InputField(default=512, description="Height of the output image")

    font_color_first: str = InputField(
        default="#FFFFFF", description="Font color for the first row of text in HEX format (e.g., '#FFFFFF')"
    )
    x_position_first: int = InputField(default=0, description="X position of the first row of text")
    y_position_first: int = InputField(default=0, description="Y position of the first row of text")
    rotation_first: int = InputField(default=0, description="Rotation angle of the first row of text (in degrees)")
    font_size_first: Optional[int] = InputField(default=35, description="Font size for the first row of text")

    font_color_second: str = InputField(
        default="#FFFFFF", description="Font color for the second row of text in HEX format (e.g., '#FFFFFF')"
    )
    x_position_second: int = InputField(default=0, description="X position of the second row of text")
    y_position_second: int = InputField(default=0, description="Y position of the second row of text")
    rotation_second: int = InputField(default=0, description="Rotation angle of the second row of text (in degrees)")
    font_size_second: Optional[int] = InputField(default=35, description="Font size for the second row of text")

    base_image: Optional[ImageField] = InputField(description="An image to place the text onto")

    def download_font(self, font_url: str) -> str:
        font_filename = font_url.split("/")[-1]
        cache_dir = "font_cache"
        font_path = f"{cache_dir}/{font_filename}"

        if not os.path.exists(cache_dir):
            os.makedirs(cache_dir)

        if not os.path.isfile(font_path):
            print("\033[1;31mFont not found in cache, downloading...\033[0m")
            response = requests.get(font_url)
            if response.status_code != 200:
                raise ValueError("Failed to download the font from the provided URL.")
            with open(font_path, "wb") as f:
                f.write(response.content)
        else:
            print("\033[1;32mFont found in cache, using cached version.\033[0m")

        return font_path

    def text_to_image_advanced(
        self,
        text_first: str,
        text_second: Optional[str],
        font_path: str,
        x1: int,
        y1: int,
        rotation1: int,
        font_size1: int,
        x2: int,
        y2: int,
        rotation2: int,
        font_size2: Optional[int],
        base_image: Optional[ImageField],
        context: InvocationContext,
    ) -> Image:
        if base_image and base_image.image_name:
            image = context.services.images.get_pil_image(base_image.image_name)
        else:
            image = Image.new("RGB", (self.image_width, self.image_height), (0, 0, 0))

        font1 = ImageFont.truetype(font_path, font_size1)
        text_img1 = Image.new("RGBA", image.size, (255, 255, 255, 0))
        d1 = ImageDraw.Draw(text_img1)
        d1.text((x1, y1), text_first, fill=self.font_color_first, font=font1)
        if rotation1 != 0:
            text_img1 = text_img1.rotate(-rotation1, resample=Image.BICUBIC, center=(x1, y1))
        image.paste(text_img1, (0, 0), text_img1)

        if text_second and font_size2:
            font2 = ImageFont.truetype(font_path, font_size2)
            text_img2 = Image.new("RGBA", image.size, (255, 255, 255, 0))
            d2 = ImageDraw.Draw(text_img2)
            d2.text((x2, y2), text_second, fill=self.font_color_second, font=font2)
            if rotation2 != 0:
                text_img2 = text_img2.rotate(-rotation2, resample=Image.BICUBIC, center=(x2, y2))
            image.paste(text_img2, (0, 0), text_img2)

        return image

    def invoke(self, context: InvocationContext) -> ImageOutput:
        if not self.text_input:
            raise ValueError("Text input is required.")

        if self.local_font:
            font_path = os.path.join("font_cache", self.local_font)
        elif self.local_font_path:
            font_path = self.local_font_path
        else:
            font_path = self.download_font(self.font_url)

        if not os.path.isfile(font_path):
            raise ValueError("Font file not found. Please check the font file path.")

        if not (10 <= self.font_size_first <= 400) or (
            self.font_size_second and not (10 <= self.font_size_second <= 400)
        ):
            raise ValueError("Font size is not within a reasonable range (10-400).")

        final_image = self.text_to_image_advanced(
            self.text_input,
            self.text_input_second_row,
            font_path,
            self.x_position_first,
            self.y_position_first,
            self.rotation_first,
            self.font_size_first,
            self.x_position_second,
            self.y_position_second,
            self.rotation_second,
            self.font_size_second,
            self.base_image,
            context,
        )

        mask_dto = context.services.images.create(
            image=final_image,
            image_origin=ResourceOrigin.INTERNAL,
            image_category=ImageCategory.GENERAL,
            node_id=self.id,
            session_id=context.graph_execution_state_id,
            is_intermediate=self.is_intermediate,
        )

        return ImageOutput(
            image=ImageField(image_name=mask_dto.image_name),
            width=mask_dto.width,
            height=mask_dto.height,
        )
