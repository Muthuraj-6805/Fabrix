import io
import os
import time
import uuid
import urllib.request

import numpy as np
import onnxruntime as ort

from PIL import Image

from flask import (
    Flask,
    render_template,
    request,
    jsonify,
    send_file,
    send_from_directory
)


# ============================================================
# FLASK CONFIGURATION
# ============================================================

app = Flask(__name__)


# ------------------------------------------------------------
# Maximum uploaded image size = 5 MB
# ------------------------------------------------------------

MAX_IMAGE_SIZE = 5 * 1024 * 1024

# Also tell Flask to reject oversized requests early.
app.config["MAX_CONTENT_LENGTH"] = MAX_IMAGE_SIZE


# ------------------------------------------------------------
# Base directory
# ------------------------------------------------------------

BASE_DIR = os.path.dirname(
    os.path.abspath(__file__)
)


# ============================================================
# CLOTHES FOLDER
# ============================================================

CLOTHES_FOLDER = os.path.join(
    BASE_DIR,
    "clothes"
)


# ============================================================
# TEMPORARY PROCESSED CLOTHING
# ============================================================

# Processed clothing images are stored only in RAM.
#
# Nothing is written to disk.
#
# Structure:
#
# temporary_clothes = {
#
#     "unique_token": {
#         "data": PNG bytes,
#         "created": timestamp
#     }
#
# }

temporary_clothes = {}


# ============================================================
# TEMPORARY IMAGE SETTINGS
# ============================================================

# 5 minutes
TEMP_IMAGE_LIFETIME = 5 * 60


# Maximum 2 processed images in RAM
MAX_TEMPORARY_IMAGES = 2


# ============================================================
# IMAGE PROCESSING LIMIT
# ============================================================

# Extremely large images can consume a lot of RAM during
# PIL / NumPy / OpenCV processing.
#
# The uploaded file is still allowed up to 5 MB.
# However, the image itself will be resized before AI
# processing if its longest side is larger than this value.
#
# This significantly reduces RAM usage on Render.

MAX_PROCESSING_DIMENSION = 1024


# ============================================================
# CREATE REQUIRED FOLDER
# ============================================================

os.makedirs(
    CLOTHES_FOLDER,
    exist_ok=True
)


# ============================================================
# AI MODEL CONFIGURATION
# ============================================================

#
# SegFormer B2 Clothes
#
# Quantized ONNX model:
#
# Xenova/segformer_b2_clothes
#

MODEL_NAME = "segformer_b2_clothes"


MODEL_URL = (
    "https://huggingface.co/"
    "Xenova/segformer_b2_clothes/"
    "resolve/main/onnx/"
    "model_quantized.onnx"
    "?download=true"
)


MODEL_FOLDER = os.path.join(
    BASE_DIR,
    "models"
)


MODEL_PATH = os.path.join(
    MODEL_FOLDER,
    "segformer_b2_clothes_quantized.onnx"
)


# ============================================================
# SEGFORMER CLASSES
# ============================================================

#
# 0  Background
# 1  Hat
# 2  Hair
# 3  Sunglasses
# 4  Upper-clothes
# 5  Skirt
# 6  Pants
# 7  Dress
# 8  Belt
# 9  Left-shoe
# 10 Right-shoe
# 11 Face
# 12 Left-leg
# 13 Right-leg
# 14 Left-arm
# 15 Right-arm
# 16 Bag
# 17 Scarf
#

BACKGROUND = 0
HAT = 1
HAIR = 2
SUNGLASSES = 3
UPPER_CLOTHES = 4
SKIRT = 5
PANTS = 6
DRESS = 7
BELT = 8
LEFT_SHOE = 9
RIGHT_SHOE = 10
FACE = 11
LEFT_LEG = 12
RIGHT_LEG = 13
LEFT_ARM = 14
RIGHT_ARM = 15
BAG = 16
SCARF = 17


# ============================================================
# CLOTHING CLASSES TO KEEP
# ============================================================

#
# These are the clothing / clothing-accessory classes
# that should remain visible.
#

CLOTHING_CLASSES = {
    UPPER_CLOTHES,
    SKIRT,
    PANTS,
    DRESS,
    BELT,
    SCARF
}


# ============================================================
# MODEL INPUT SETTINGS
# ============================================================

MODEL_INPUT_WIDTH = 512
MODEL_INPUT_HEIGHT = 512


IMAGE_MEAN = np.array(
    [0.485, 0.456, 0.406],
    dtype=np.float32
)


IMAGE_STD = np.array(
    [0.229, 0.224, 0.225],
    dtype=np.float32
)


# ============================================================
# STARTUP INFORMATION
# ============================================================

print("\n========================================")
print("           FABRIX")
print("      VIRTUAL TRY ON SERVER")
print("========================================")

print("\nSegmentation model:")
print(MODEL_NAME)

print("\nUpload limit:")
print("5 MB")

print("\nTemporary image lifetime:")
print("5 minutes")

print("\nMaximum temporary images:")
print("2")

print("\nMaximum processing dimension:")
print(f"{MAX_PROCESSING_DIMENSION}px")


# ============================================================
# DOWNLOAD MODEL IF NECESSARY
# ============================================================

def download_model_if_needed():

    os.makedirs(
        MODEL_FOLDER,
        exist_ok=True
    )

    if os.path.exists(MODEL_PATH):

        print(
            "\nSegFormer model already exists."
        )

        print(
            "Model path:",
            MODEL_PATH
        )

        return

    print(
        "\nDownloading SegFormer B2 "
        "quantized ONNX model..."
    )

    print(
        "Approximately 28.8 MB."
    )

    temporary_model_path = (
        MODEL_PATH + ".download"
    )

    try:

        urllib.request.urlretrieve(
            MODEL_URL,
            temporary_model_path
        )

        os.replace(
            temporary_model_path,
            MODEL_PATH
        )

        print(
            "\nSegFormer model downloaded successfully."
        )

    except Exception as error:

        if os.path.exists(
            temporary_model_path
        ):

            try:

                os.remove(
                    temporary_model_path
                )

            except Exception:
                pass

        raise RuntimeError(
            "Unable to download SegFormer model: "
            + str(error)
        )


# ============================================================
# LOAD ONNX MODEL
# ============================================================

print(
    "\nLoading SegFormer AI model..."
)

download_model_if_needed()


# ------------------------------------------------------------
# Configure ONNX Runtime for low memory usage.
# ------------------------------------------------------------

session_options = ort.SessionOptions()


# Only one thread.
session_options.intra_op_num_threads = 1
session_options.inter_op_num_threads = 1


# Sequential execution generally uses less memory.
session_options.execution_mode = (
    ort.ExecutionMode.ORT_SEQUENTIAL
)


# Basic optimization instead of full optimization.
#
# This reduces startup memory pressure.
session_options.graph_optimization_level = (
    ort.GraphOptimizationLevel.ORT_ENABLE_BASIC
)


# Disable memory pattern optimization.
#
# This can reduce retained memory for this
# small single-request server.
session_options.enable_mem_pattern = False


# Disable CPU memory arena.
#
# This prevents ONNX Runtime from keeping a large
# reusable memory arena after inference.
session_options.enable_cpu_mem_arena = False


try:

    segmentation_session = ort.InferenceSession(
        MODEL_PATH,
        sess_options=session_options,
        providers=[
            "CPUExecutionProvider"
        ]
    )

except Exception as error:

    print(
        "\nERROR loading SegFormer model:"
    )

    print(
        str(error)
    )

    raise


# ============================================================
# MODEL INPUT / OUTPUT INFORMATION
# ============================================================

MODEL_INPUT_NAME = (
    segmentation_session
    .get_inputs()[0]
    .name
)


MODEL_OUTPUTS = (
    segmentation_session
    .get_outputs()
)


if not MODEL_OUTPUTS:

    raise RuntimeError(
        "SegFormer model has no outputs."
    )


MODEL_OUTPUT_NAME = (
    MODEL_OUTPUTS[0].name
)


print(
    "\nSegFormer model loaded successfully."
)

print(
    "Input name:",
    MODEL_INPUT_NAME
)

print(
    "Output name:",
    MODEL_OUTPUT_NAME
)


# ============================================================
# PREPARE IMAGE FOR SEGFORMER
# ============================================================

def prepare_model_input(image):

    # --------------------------------------------------------
    # Convert to RGB
    # --------------------------------------------------------

    image = image.convert("RGB")


    # --------------------------------------------------------
    # Resize to 512 x 512
    # --------------------------------------------------------

    resized = image.resize(
        (
            MODEL_INPUT_WIDTH,
            MODEL_INPUT_HEIGHT
        ),
        Image.Resampling.BILINEAR
    )


    # --------------------------------------------------------
    # Convert to float32
    # --------------------------------------------------------

    image_array = np.asarray(
        resized,
        dtype=np.float32
    )


    # --------------------------------------------------------
    # Normalize from 0-255 to 0-1
    # --------------------------------------------------------

    image_array *= (
        1.0 / 255.0
    )


    # --------------------------------------------------------
    # ImageNet normalization
    # --------------------------------------------------------

    image_array -= IMAGE_MEAN
    image_array /= IMAGE_STD


    # --------------------------------------------------------
    # HWC -> CHW
    # --------------------------------------------------------

    image_array = np.transpose(
        image_array,
        (2, 0, 1)
    )


    # --------------------------------------------------------
    # CHW -> NCHW
    # --------------------------------------------------------

    image_array = np.expand_dims(
        image_array,
        axis=0
    )


    # --------------------------------------------------------
    # Make contiguous.
    # --------------------------------------------------------

    return np.ascontiguousarray(
        image_array,
        dtype=np.float32
    )


# ============================================================
# OUTPUT -> CLASS MAP
# ============================================================

def convert_model_output_to_class_map(
    output,
    original_width,
    original_height
):

    output = np.asarray(
        output
    )


    # --------------------------------------------------------
    # Expected:
    #
    # [1, classes, height, width]
    #
    # or:
    #
    # [classes, height, width]
    # --------------------------------------------------------

    if output.ndim == 4:

        if output.shape[0] != 1:

            raise ValueError(
                "Unexpected SegFormer batch size: "
                + str(output.shape)
            )

        logits = output[0]

    elif output.ndim == 3:

        logits = output

    else:

        raise ValueError(
            "Unexpected SegFormer output shape: "
            + str(output.shape)
        )


    # --------------------------------------------------------
    # Argmax.
    #
    # This creates a compact uint8 class map.
    # --------------------------------------------------------

    class_map = np.argmax(
        logits,
        axis=0
    ).astype(
        np.uint8
    )


    # --------------------------------------------------------
    # Release logits as soon as possible.
    # --------------------------------------------------------

    del logits


    # --------------------------------------------------------
    # Resize class IDs.
    #
    # NEAREST is required because class IDs must not
    # be interpolated.
    # --------------------------------------------------------

    class_map_image = Image.fromarray(
        class_map,
        mode="L"
    )


    del class_map


    class_map_image = class_map_image.resize(
        (
            original_width,
            original_height
        ),
        Image.Resampling.NEAREST
    )


    return np.asarray(
        class_map_image,
        dtype=np.uint8
    )


# ============================================================
# CREATE CLOTHING MASK
# ============================================================

def create_clothing_mask(
    class_map
):

    mask = np.zeros(
        class_map.shape,
        dtype=np.uint8
    )


    # --------------------------------------------------------
    # Keep only clothing classes.
    # --------------------------------------------------------

    for class_id in CLOTHING_CLASSES:

        mask[
            class_map == class_id
        ] = 255


    return mask


# ============================================================
# RESIZE LARGE IMAGE
# ============================================================

def resize_for_processing(image):

    width, height = image.size


    longest_side = max(
        width,
        height
    )


    if longest_side <= MAX_PROCESSING_DIMENSION:

        return image


    scale = (
        MAX_PROCESSING_DIMENSION
        / float(longest_side)
    )


    new_width = max(
        1,
        int(width * scale)
    )


    new_height = max(
        1,
        int(height * scale)
    )


    print(
        "Large image detected."
    )

    print(
        "Resizing from:",
        image.size
    )

    print(
        "Resizing to:",
        (new_width, new_height)
    )


    return image.resize(
        (
            new_width,
            new_height
        ),
        Image.Resampling.LANCZOS
    )


# ============================================================
# SEGMENT IMAGE
# ============================================================

def segment_image(image):

    print(
        "Preparing image for SegFormer..."
    )


    # --------------------------------------------------------
    # Reduce very large images before creating NumPy arrays.
    # --------------------------------------------------------

    processing_image = resize_for_processing(
        image
    )


    original_width = processing_image.width
    original_height = processing_image.height


    # --------------------------------------------------------
    # Prepare model input.
    # --------------------------------------------------------

    model_input = prepare_model_input(
        processing_image
    )


    print(
        "Running SegFormer inference..."
    )


    try:

        outputs = segmentation_session.run(
            [
                MODEL_OUTPUT_NAME
            ],
            {
                MODEL_INPUT_NAME:
                    model_input
            }
        )

    finally:

        # Release input immediately.
        del model_input


    if not outputs:

        raise ValueError(
            "SegFormer returned no output."
        )


    raw_output = outputs[0]


    print(
        "SegFormer output shape:",
        raw_output.shape
    )


    # --------------------------------------------------------
    # Convert model output to class map.
    # --------------------------------------------------------

    class_map = (
        convert_model_output_to_class_map(
            raw_output,
            original_width,
            original_height
        )
    )


    # --------------------------------------------------------
    # Release raw ONNX output.
    # --------------------------------------------------------

    del raw_output
    del outputs


    # --------------------------------------------------------
    # Convert to clothing-only mask.
    # --------------------------------------------------------

    mask = create_clothing_mask(
        class_map
    )


    del class_map


    # --------------------------------------------------------
    # Return mask and processing image.
    # --------------------------------------------------------

    return (
        processing_image,
        mask
    )


# ============================================================
# CLEAN MASK
# ============================================================

def clean_mask(mask):

    import cv2


    mask = np.asarray(
        mask,
        dtype=np.uint8
    )


    # --------------------------------------------------------
    # Remove tiny isolated regions.
    # --------------------------------------------------------

    kernel_small = np.ones(
        (3, 3),
        np.uint8
    )


    mask = cv2.morphologyEx(
        mask,
        cv2.MORPH_OPEN,
        kernel_small
    )


    # --------------------------------------------------------
    # Fill small gaps.
    # --------------------------------------------------------

    kernel_medium = np.ones(
        (7, 7),
        np.uint8
    )


    mask = cv2.morphologyEx(
        mask,
        cv2.MORPH_CLOSE,
        kernel_medium
    )


    # --------------------------------------------------------
    # Smooth edges.
    # --------------------------------------------------------

    mask = cv2.GaussianBlur(
        mask,
        (5, 5),
        0
    )


    return mask


# ============================================================
# CREATE TRANSPARENT PNG
# ============================================================

def create_transparent_image(
    image,
    mask
):

    # --------------------------------------------------------
    # Convert to RGBA.
    # --------------------------------------------------------

    image = image.convert(
        "RGBA"
    )


    image_array = np.asarray(
        image
    ).copy()


    # --------------------------------------------------------
    # Validate mask.
    # --------------------------------------------------------

    expected_shape = (
        image.height,
        image.width
    )


    mask = np.asarray(
        mask,
        dtype=np.uint8
    )


    if mask.shape != expected_shape:

        raise ValueError(
            "Mask/image size mismatch. "
            f"Mask: {mask.shape}, "
            f"Image: {expected_shape}"
        )


    # --------------------------------------------------------
    # Set alpha channel.
    # --------------------------------------------------------

    image_array[:, :, 3] = mask


    result = Image.fromarray(
        image_array,
        "RGBA"
    )


    del image_array


    return result


# ============================================================
# CROP TO SELECTED AREA
# ============================================================

def crop_to_selected_area(
    image,
    mask
):

    ys, xs = np.where(
        mask > 20
    )


    # --------------------------------------------------------
    # Nothing detected.
    # --------------------------------------------------------

    if (
        len(xs) == 0
        or
        len(ys) == 0
    ):

        return image


    # --------------------------------------------------------
    # Bounding box.
    # --------------------------------------------------------

    min_x = max(
        0,
        int(xs.min()) - 10
    )


    max_x = min(
        image.width,
        int(xs.max()) + 11
    )


    min_y = max(
        0,
        int(ys.min()) - 10
    )


    max_y = min(
        image.height,
        int(ys.max()) + 11
    )


    return image.crop(
        (
            min_x,
            min_y,
            max_x,
            max_y
        )
    )


# ============================================================
# PROCESS IMAGE
# ============================================================

def process_image(image):

    print(
        "\n----------------------------------------"
    )

    print(
        "Processing clothing image..."
    )

    print(
        "----------------------------------------"
    )

    print(
        "Original size:",
        image.size
    )


    # --------------------------------------------------------
    # Segment.
    # --------------------------------------------------------

    print(
        "Running clothing segmentation..."
    )


    processing_image, mask = segment_image(
        image
    )


    # --------------------------------------------------------
    # Release original image if it is a separate object.
    # --------------------------------------------------------

    del image


    # --------------------------------------------------------
    # Clean mask.
    # --------------------------------------------------------

    print(
        "Cleaning segmentation..."
    )


    mask = clean_mask(
        mask
    )


    # --------------------------------------------------------
    # Create transparent image.
    # --------------------------------------------------------

    print(
        "Creating transparent PNG..."
    )


    result = create_transparent_image(
        processing_image,
        mask
    )


    # --------------------------------------------------------
    # Crop.
    # --------------------------------------------------------

    print(
        "Cropping result..."
    )


    result = crop_to_selected_area(
        result,
        mask
    )


    # --------------------------------------------------------
    # Release temporary arrays.
    # --------------------------------------------------------

    del processing_image
    del mask


    print(
        "Final size:",
        result.size
    )

    print(
        "Processing complete."
    )


    return result


# ============================================================
# CLEAN EXPIRED TEMPORARY IMAGES
# ============================================================

def cleanup_expired_images():

    current_time = time.time()

    expired_tokens = []


    for token, item in list(
        temporary_clothes.items()
    ):

        created_time = item["created"]


        if (
            current_time - created_time
            >
            TEMP_IMAGE_LIFETIME
        ):

            expired_tokens.append(
                token
            )


    for token in expired_tokens:

        temporary_clothes.pop(
            token,
            None
        )


    if expired_tokens:

        print(
            f"Removed {len(expired_tokens)} "
            "expired temporary clothing image(s)."
        )


# ============================================================
# STORE TEMPORARY PROCESSED IMAGE
# ============================================================

def store_temporary_image(
    image_data
):

    cleanup_expired_images()


    # --------------------------------------------------------
    # Prevent unlimited RAM usage.
    # --------------------------------------------------------

    if (
        len(temporary_clothes)
        >= MAX_TEMPORARY_IMAGES
    ):

        oldest_token = min(
            temporary_clothes,
            key=lambda token:
                temporary_clothes[token]["created"]
        )


        temporary_clothes.pop(
            oldest_token,
            None
        )


        print(
            "Removed oldest temporary image "
            "because the RAM limit was reached."
        )


    # --------------------------------------------------------
    # Generate unique token.
    # --------------------------------------------------------

    token = uuid.uuid4().hex


    # --------------------------------------------------------
    # Store image in RAM.
    # --------------------------------------------------------

    temporary_clothes[token] = {
        "data": image_data,
        "created": time.time()
    }


    return token


# ============================================================
# HOME PAGE
# ============================================================

@app.route("/")
def index():

    return render_template(
        "index.html"
    )


# ============================================================
# LIVE TRY-ON PAGE
# ============================================================

@app.route("/try-on")
def try_on():

    return render_template(
        "try_on.html"
    )


# ============================================================
# CLOTHES API
# ============================================================

@app.route(
    "/clothes",
    methods=["GET"]
)
def get_clothes():

    clothes = []


    allowed_extensions = {
        ".jpg",
        ".jpeg",
        ".png",
        ".webp"
    }


    try:

        filenames = os.listdir(
            CLOTHES_FOLDER
        )

    except Exception as error:

        print(
            "Error reading clothes folder:",
            error
        )

        return jsonify([])


    for filename in sorted(
        filenames,
        key=str.lower
    ):

        file_path = os.path.join(
            CLOTHES_FOLDER,
            filename
        )


        if not os.path.isfile(
            file_path
        ):

            continue


        extension = os.path.splitext(
            filename
        )[1].lower()


        if extension not in allowed_extensions:

            continue


        clothes.append(
            {
                "name": filename,
                "url": "/clothes/" + filename
            }
        )


    return jsonify(
        clothes
    )


# ============================================================
# SERVE CLOTHING IMAGES
# ============================================================

@app.route(
    "/clothes/<path:filename>"
)
def serve_clothing(
    filename
):

    return send_from_directory(
        CLOTHES_FOLDER,
        filename
    )


# ============================================================
# PROCESS UPLOADED CLOTHING
# ============================================================

@app.route(
    "/process",
    methods=["POST"]
)
def process():

    try:

        # ----------------------------------------------------
        # Check file.
        # ----------------------------------------------------

        if "image" not in request.files:

            return jsonify(
                {
                    "success": False,
                    "error":
                        "No image was provided."
                }
            ), 400


        file = request.files["image"]


        if (
            not file
            or
            file.filename == ""
        ):

            return jsonify(
                {
                    "success": False,
                    "error":
                        "Invalid image."
                }
            ), 400


        # ----------------------------------------------------
        # Read image.
        # ----------------------------------------------------

        image_data = file.read()


        if len(image_data) == 0:

            return jsonify(
                {
                    "success": False,
                    "error":
                        "The image is empty."
                }
            ), 400


        # ----------------------------------------------------
        # 5 MB size limit.
        # ----------------------------------------------------

        if len(image_data) > MAX_IMAGE_SIZE:

            return jsonify(
                {
                    "success": False,
                    "error":
                        "Image is too large. "
                        "Maximum size is 5 MB."
                }
            ), 400


        # ----------------------------------------------------
        # Open image.
        # ----------------------------------------------------

        try:

            image = Image.open(
                io.BytesIO(
                    image_data
                )
            )

            image.load()

        except Exception:

            return jsonify(
                {
                    "success": False,
                    "error":
                        "The uploaded file is not a valid image."
                }
            ), 400


        # ----------------------------------------------------
        # Release original uploaded bytes.
        # ----------------------------------------------------

        del image_data


        # ----------------------------------------------------
        # Convert to RGB.
        # ----------------------------------------------------

        image = image.convert(
            "RGB"
        )


        # ----------------------------------------------------
        # Process image.
        # ----------------------------------------------------

        result = process_image(
            image
        )


        # ----------------------------------------------------
        # Convert result to PNG.
        # ----------------------------------------------------

        output_buffer = io.BytesIO()


        result.save(
            output_buffer,
            format="PNG",
            optimize=True
        )


        output_buffer.seek(0)


        # ----------------------------------------------------
        # Get PNG bytes.
        # ----------------------------------------------------

        processed_data = (
            output_buffer.getvalue()
        )


        # ----------------------------------------------------
        # Release PIL objects.
        # ----------------------------------------------------

        output_buffer.close()

        result.close()


        # ----------------------------------------------------
        # Store processed image in RAM.
        # ----------------------------------------------------

        token = store_temporary_image(
            processed_data
        )


        # ----------------------------------------------------
        # Create temporary URL.
        # ----------------------------------------------------

        image_url = (
            "/temporary-clothes/"
            + token
        )


        print(
            "\nProcessed clothing stored "
            "temporarily in RAM."
        )

        print(
            "Temporary URL:",
            image_url
        )

        print(
            "Temporary images currently stored:",
            len(temporary_clothes)
        )


        # ----------------------------------------------------
        # Return JSON.
        # ----------------------------------------------------

        return jsonify(
            {
                "success": True,
                "url": image_url
            }
        )


    except Exception as error:

        print(
            "\nERROR:",
            str(error)
        )

        return jsonify(
            {
                "success": False,
                "error":
                    "An error occurred while processing the image."
            }
        ), 500


# ============================================================
# HANDLE FLASK 413
# ============================================================

@app.errorhandler(413)
def request_entity_too_large(error):

    return jsonify(
        {
            "success": False,
            "error":
                "Image is too large. Maximum size is 5 MB."
        }
    ), 413


# ============================================================
# SERVE TEMPORARY PROCESSED CLOTHING
# ============================================================

@app.route(
    "/temporary-clothes/<token>"
)
def serve_temporary_clothing(
    token
):

    # --------------------------------------------------------
    # Remove expired images first.
    # --------------------------------------------------------

    cleanup_expired_images()


    # --------------------------------------------------------
    # Find image.
    # --------------------------------------------------------

    item = temporary_clothes.get(
        token
    )


    # --------------------------------------------------------
    # Image missing / expired.
    # --------------------------------------------------------

    if item is None:

        return jsonify(
            {
                "success": False,
                "error":
                    "This processed clothing image "
                    "has expired or does not exist."
            }
        ), 404


    # --------------------------------------------------------
    # Return PNG directly from RAM.
    # --------------------------------------------------------

    return send_file(
        io.BytesIO(
            item["data"]
        ),
        mimetype="image/png",
        as_attachment=False,
        download_name="clothing.png"
    )


# ============================================================
# RUN SERVER
# ============================================================

if __name__ == "__main__":

    print(
        "\n========================================"
    )

    print(
        "           FABRIX"
    )

    print(
        "      VIRTUAL TRY ON SERVER"
    )

    print(
        "========================================"
    )

    print(
        "\nAI model:"
    )

    print(
        MODEL_NAME
    )

    print(
        "\nClothing classes kept:"
    )

    print(
        "Upper-clothes, Skirt, Pants, "
        "Dress, Belt, Scarf"
    )

    print(
        "\nUpload limit:"
    )

    print(
        "5 MB"
    )

    print(
        "\nUploaded processed clothing:"
    )

    print(
        "Temporary RAM storage only"
    )

    print(
        "\nTemporary image lifetime:"
    )

    print(
        f"{TEMP_IMAGE_LIFETIME // 60} minutes"
    )

    print(
        "\nMaximum temporary images:"
    )

    print(
        MAX_TEMPORARY_IMAGES
    )

    print(
        "\nOpen in browser:"
    )

    print(
        "http://127.0.0.1:5000"
    )

    print(
        "\nPress CTRL+C to stop the server."
    )


    app.run(
        host="127.0.0.1",
        port=5000,
        debug=False
    )
