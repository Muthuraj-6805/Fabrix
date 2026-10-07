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

# Maximum uploaded image size = 20 MB
MAX_IMAGE_SIZE = 20 * 1024 * 1024

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

#
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
#

temporary_clothes = {}


# ============================================================
# TEMPORARY IMAGE SETTINGS
# ============================================================

# 10 minutes
TEMP_IMAGE_LIFETIME = 10 * 60

# Maximum 50 processed images in RAM
MAX_TEMPORARY_IMAGES = 50


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
# The quantized model is approximately 28.8 MB.
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
# SEGFORMER CONFIGURATION
# ============================================================

#
# The model has 18 classes.
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


# ------------------------------------------------------------
# Classes that should remain visible.
#
# These are clothing / clothing-accessory classes.
#
# We intentionally DO NOT include:
#
# Background
# Hat
# Hair
# Sunglasses
# Shoes
# Face
# Legs
# Arms
# Bag
#
# because the goal is to extract the clothing item.
# ------------------------------------------------------------

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

#
# SegFormer B2 Clothes uses a 512 x 512 image processor
# configuration.
#

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
        "This is approximately 28.8 MB."
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
# Configure ONNX Runtime to use CPU.
#
# We deliberately use one thread to reduce memory usage on
# Render Free.
# ------------------------------------------------------------

session_options = ort.SessionOptions()

session_options.intra_op_num_threads = 1
session_options.inter_op_num_threads = 1

session_options.execution_mode = (
    ort.ExecutionMode.ORT_SEQUENTIAL
)

session_options.graph_optimization_level = (
    ort.GraphOptimizationLevel.ORT_ENABLE_ALL
)


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


# ------------------------------------------------------------
# Get model input/output names.
# ------------------------------------------------------------

MODEL_INPUT_NAME = (
    segmentation_session
    .get_inputs()[0]
    .name
)

MODEL_OUTPUTS = (
    segmentation_session
    .get_outputs()
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

    image = image.convert(
        "RGB"
    )

    # --------------------------------------------------------
    # Resize to model input size.
    #
    # SegFormer B2 uses 512 x 512 preprocessing.
    # --------------------------------------------------------

    resized = image.resize(
        (
            MODEL_INPUT_WIDTH,
            MODEL_INPUT_HEIGHT
        ),
        Image.Resampling.BILINEAR
    )

    # --------------------------------------------------------
    # Convert to float32 NumPy array
    # --------------------------------------------------------

    image_array = np.asarray(
        resized,
        dtype=np.float32
    )

    # --------------------------------------------------------
    # Convert [0, 255] -> [0, 1]
    # --------------------------------------------------------

    image_array = (
        image_array / 255.0
    )

    # --------------------------------------------------------
    # Normalize using ImageNet mean/std.
    # --------------------------------------------------------

    image_array = (
        image_array - IMAGE_MEAN
    ) / IMAGE_STD

    # --------------------------------------------------------
    # HWC -> CHW
    # --------------------------------------------------------

    image_array = np.transpose(
        image_array,
        (2, 0, 1)
    )

    # --------------------------------------------------------
    # Add batch dimension
    #
    # CHW -> NCHW
    # --------------------------------------------------------

    image_array = np.expand_dims(
        image_array,
        axis=0
    )

    return np.ascontiguousarray(
        image_array,
        dtype=np.float32
    )


# ============================================================
# SEGFORMER OUTPUT -> CLASS MASK
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
    # Expected semantic-segmentation output is normally:
    #
    # [batch, classes, height, width]
    #
    # Example:
    #
    # [1, 18, H, W]
    # --------------------------------------------------------

    if output.ndim == 4:

        if output.shape[0] != 1:

            raise ValueError(
                "Unexpected SegFormer batch size: "
                + str(output.shape)
            )

        # ----------------------------------------------------
        # Argmax across class/channel dimension.
        # ----------------------------------------------------

        class_map = np.argmax(
            output[0],
            axis=0
        ).astype(
            np.uint8
        )

    elif output.ndim == 3:

        #
        # Some ONNX exports may remove the batch dimension.
        #
        # Handle:
        #
        # [classes, H, W]
        #

        class_map = np.argmax(
            output,
            axis=0
        ).astype(
            np.uint8
        )

    else:

        raise ValueError(
            "Unexpected SegFormer output shape: "
            + str(output.shape)
        )

    # --------------------------------------------------------
    # Convert class map to PIL image.
    # --------------------------------------------------------

    class_map_image = Image.fromarray(
        class_map,
        mode="L"
    )

    # --------------------------------------------------------
    # Resize class labels to original image dimensions.
    #
    # IMPORTANT:
    #
    # NEAREST is used because class IDs must not be
    # interpolated.
    # --------------------------------------------------------

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

    # --------------------------------------------------------
    # Start with completely transparent/removed mask.
    # --------------------------------------------------------

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
# SEGMENT IMAGE
# ============================================================

def segment_image(image):

    """
    Segment the uploaded image using SegFormer B2 Clothes.

    The model predicts semantic classes such as:

        Upper-clothes
        Skirt
        Pants
        Dress
        Belt
        Scarf

    The final mask keeps only those clothing classes.

    Background, head, face, hair, arms, legs, shoes, etc.
    are removed.
    """

    print(
        "Preparing image for SegFormer..."
    )

    model_input = prepare_model_input(
        image
    )

    # --------------------------------------------------------
    # Run ONNX inference
    # --------------------------------------------------------

    print(
        "Running SegFormer inference..."
    )

    outputs = segmentation_session.run(
        None,
        {
            MODEL_INPUT_NAME:
                model_input
        }
    )

    if not outputs:

        raise ValueError(
            "SegFormer returned no output."
        )

    # --------------------------------------------------------
    # Get segmentation output.
    # --------------------------------------------------------

    raw_output = outputs[0]

    print(
        "SegFormer output shape:",
        raw_output.shape
    )

    # --------------------------------------------------------
    # Convert logits to class map.
    # --------------------------------------------------------

    class_map = (
        convert_model_output_to_class_map(
            raw_output,
            image.width,
            image.height
        )
    )

    # --------------------------------------------------------
    # Convert class map to clothing-only mask.
    # --------------------------------------------------------

    mask = create_clothing_mask(
        class_map
    )

    # --------------------------------------------------------
    # Validate shape.
    # --------------------------------------------------------

    expected_shape = (
        image.height,
        image.width
    )

    if mask.shape != expected_shape:

        raise ValueError(
            "Invalid clothing mask shape: "
            f"{mask.shape}. "
            f"Expected: {expected_shape}."
        )

    return mask


# ============================================================
# CLEAN MASK
# ============================================================

def clean_mask(mask):

    import cv2

    # --------------------------------------------------------
    # Make sure mask is uint8.
    # --------------------------------------------------------

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
    # Convert original image to RGBA.
    # --------------------------------------------------------

    image = image.convert(
        "RGBA"
    )

    image_array = np.array(
        image
    )

    # --------------------------------------------------------
    # Validate mask size.
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
    # Set mask as alpha channel.
    #
    # 255 = visible
    # 0   = transparent
    # --------------------------------------------------------

    image_array[:, :, 3] = mask

    result = Image.fromarray(
        image_array,
        "RGBA"
    )

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

    mask = segment_image(
        image
    )

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
        image,
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
    # Final information.
    # --------------------------------------------------------

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

    for token, item in temporary_clothes.items():

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

    # --------------------------------------------------------
    # Supported image extensions.
    # --------------------------------------------------------

    allowed_extensions = {
        ".jpg",
        ".jpeg",
        ".png",
        ".webp"
    }

    # --------------------------------------------------------
    # Read clothes folder.
    # --------------------------------------------------------

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

    # --------------------------------------------------------
    # Create clothing list.
    # --------------------------------------------------------

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

#
# IMPORTANT:
#
# Uploaded image is processed in memory.
#
# Processed PNG is stored temporarily in RAM.
#
# Nothing is saved to disk.
#

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
        # Read image into memory.
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
        # 20 MB size limit.
        # ----------------------------------------------------

        if len(image_data) > MAX_IMAGE_SIZE:

            return jsonify(
                {
                    "success": False,
                    "error":
                        "Image is too large. "
                        "Maximum size is 20 MB."
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
            format="PNG"
        )

        output_buffer.seek(0)

        # ----------------------------------------------------
        # Get PNG bytes.
        # ----------------------------------------------------

        processed_data = (
            output_buffer.getvalue()
        )

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
        "\nClothes folder:"
    )

    print(
        CLOTHES_FOLDER
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
