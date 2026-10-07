import io
import os
import time
import uuid

import numpy as np
import torch

from PIL import Image

from flask import (
    Flask,
    render_template,
    request,
    jsonify,
    send_file,
    send_from_directory
)

from transformers import (
    AutoImageProcessor,
    SegformerForSemanticSegmentation
)


# ============================================================
# FLASK CONFIGURATION
# ============================================================

app = Flask(__name__)

MAX_IMAGE_SIZE = 20 * 1024 * 1024  # 20 MB

BASE_DIR = os.path.dirname(
    os.path.abspath(__file__)
)


# ============================================================
# CLOTHES FOLDER
# ============================================================
#
# This folder contains your permanent/default clothing images.
#
# Example:
#
# clothes/
#   shirt.png
#   jeans.png
#   dress.png
#
# Uploaded user clothing is NOT saved here.
# ============================================================

CLOTHES_FOLDER = os.path.join(
    BASE_DIR,
    "clothes"
)


# ============================================================
# TEMPORARY PROCESSED CLOTHING
# ============================================================
#
# Uploaded clothing is processed and temporarily stored
# in server RAM.
#
# NOTHING is written to disk.
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
# ============================================================

temporary_clothes = {}


# ============================================================
# TEMPORARY IMAGE SETTINGS
# ============================================================

# Temporary images are automatically considered expired
# after 10 minutes.

TEMP_IMAGE_LIFETIME = 10 * 60


# Maximum number of processed images kept in RAM.

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

MODEL_NAME = "mattmdjaga/segformer_b2_clothes"


print("\n========================================")
print("           FABRIX")
print("      VIRTUAL TRY ON SERVER")
print("========================================")

print("\nLoading AI model...")


# ============================================================
# DEVICE
# ============================================================

device = (
    "cuda"
    if torch.cuda.is_available()
    else "cpu"
)

print("Device:", device)


# ============================================================
# LOAD PROCESSOR
# ============================================================

processor = AutoImageProcessor.from_pretrained(
    MODEL_NAME
)


# ============================================================
# LOAD MODEL
# ============================================================

model = SegformerForSemanticSegmentation.from_pretrained(
    MODEL_NAME
)

model.to(device)

model.eval()

print("AI model loaded successfully.")


# ============================================================
# CLASSES TO KEEP
# ============================================================

# Model classes:
#
# 0  = Background
# 1  = Hat
# 2  = Hair
# 3  = Sunglasses
# 4  = Upper-clothes
# 5  = Skirt
# 6  = Pants
# 7  = Dress
# 8  = Belt
# 9  = Left-shoe
# 10 = Right-shoe
# 11 = Face
# 12 = Left-leg
# 13 = Right-leg
# 14 = Left-arm
# 15 = Right-arm
# 16 = Bag
# 17 = Scarf
#
# We keep:
#
# Upper-clothes
# Skirt
# Pants
# Dress
# Left-arm
# Right-arm
#
# Everything else becomes transparent.


KEEP_CLASSES = {
    "upper-clothes",
    "skirt",
    "pants",
    "dress",
    "left-arm",
    "right-arm"
}


# ============================================================
# FIND CLASS IDS
# ============================================================

id2label = model.config.id2label

KEEP_IDS = []


for class_id, label in id2label.items():

    label_lower = str(label).lower()

    if label_lower in KEEP_CLASSES:

        KEEP_IDS.append(
            int(class_id)
        )


print("\nClasses being kept:")

for class_id in KEEP_IDS:

    print(
        f"  {class_id} = {id2label[class_id]}"
    )


# ============================================================
# SEGMENT IMAGE
# ============================================================

def segment_image(image):

    original_width, original_height = image.size


    # --------------------------------------------------------
    # Prepare image for model
    # --------------------------------------------------------

    inputs = processor(
        images=image,
        return_tensors="pt"
    )


    inputs = {
        key: value.to(device)
        for key, value in inputs.items()
    }


    # --------------------------------------------------------
    # Run model
    # --------------------------------------------------------

    with torch.no_grad():

        outputs = model(
            **inputs
        )


    logits = outputs.logits


    # --------------------------------------------------------
    # Resize model output
    # --------------------------------------------------------

    logits = torch.nn.functional.interpolate(
        logits,
        size=(
            original_height,
            original_width
        ),
        mode="bilinear",
        align_corners=False
    )


    # --------------------------------------------------------
    # Get class with highest probability
    # --------------------------------------------------------

    prediction = logits.argmax(
        dim=1
    )[0]


    # --------------------------------------------------------
    # Create empty mask
    # --------------------------------------------------------

    mask = torch.zeros(
        (
            original_height,
            original_width
        ),
        dtype=torch.uint8,
        device=device
    )


    # --------------------------------------------------------
    # Keep selected classes
    # --------------------------------------------------------

    for class_id in KEEP_IDS:

        mask[
            prediction == class_id
        ] = 255


    return mask.cpu().numpy()


# ============================================================
# CLEAN MASK
# ============================================================

def clean_mask(mask):

    import cv2


    # --------------------------------------------------------
    # Remove tiny isolated regions
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
    # Fill small gaps
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
    # Smooth edges
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

    image = image.convert(
        "RGBA"
    )


    image_array = np.array(
        image
    )


    # --------------------------------------------------------
    # Mask becomes alpha channel
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
    # Nothing detected
    # --------------------------------------------------------

    if (
        len(xs) == 0
        or
        len(ys) == 0
    ):

        return image


    # --------------------------------------------------------
    # Bounding box
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

    print("\n----------------------------------------")
    print("Processing clothing image...")
    print("----------------------------------------")


    print(
        "Original size:",
        image.size
    )


    # --------------------------------------------------------
    # Segment
    # --------------------------------------------------------

    print(
        "Running clothing segmentation..."
    )


    mask = segment_image(
        image
    )


    # --------------------------------------------------------
    # Clean mask
    # --------------------------------------------------------

    print(
        "Cleaning segmentation..."
    )


    mask = clean_mask(
        mask
    )


    # --------------------------------------------------------
    # Create transparent image
    # --------------------------------------------------------

    print(
        "Creating transparent PNG..."
    )


    result = create_transparent_image(
        image,
        mask
    )


    # --------------------------------------------------------
    # Crop
    # --------------------------------------------------------

    print(
        "Cropping result..."
    )


    result = crop_to_selected_area(
        result,
        mask
    )


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
            > TEMP_IMAGE_LIFETIME
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
    # Prevent unlimited RAM usage
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
    # Generate unique token
    # --------------------------------------------------------

    token = uuid.uuid4().hex


    # --------------------------------------------------------
    # Store image in RAM
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
    # Supported image extensions
    # --------------------------------------------------------

    allowed_extensions = {
        ".jpg",
        ".jpeg",
        ".png",
        ".webp"
    }


    # --------------------------------------------------------
    # Read clothes folder
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
    # Create clothing list
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
# The uploaded image is processed in memory.
#
# The processed image is then temporarily stored in RAM.
#
# NOTHING is saved to disk.
#
# ============================================================

@app.route(
    "/process",
    methods=["POST"]
)
def process():

    try:

        # ----------------------------------------------------
        # Check file
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
        # Read image into memory
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
        # Size limit
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
        # Open image
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
        # Convert to RGB
        # ----------------------------------------------------

        image = image.convert(
            "RGB"
        )


        # ----------------------------------------------------
        # Process image
        # ----------------------------------------------------

        result = process_image(
            image
        )


        # ----------------------------------------------------
        # Convert processed image to PNG
        # ----------------------------------------------------

        output_buffer = io.BytesIO()


        result.save(
            output_buffer,
            format="PNG"
        )


        output_buffer.seek(0)


        # ----------------------------------------------------
        # Get PNG bytes
        # ----------------------------------------------------

        processed_data = (
            output_buffer.getvalue()
        )


        # ----------------------------------------------------
        # Store temporarily in RAM
        # ----------------------------------------------------

        token = store_temporary_image(
            processed_data
        )


        # ----------------------------------------------------
        # Create short temporary URL
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
        # Return JSON
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
    # Remove expired images first
    # --------------------------------------------------------

    cleanup_expired_images()


    # --------------------------------------------------------
    # Find image
    # --------------------------------------------------------

    item = temporary_clothes.get(
        token
    )


    # --------------------------------------------------------
    # Image missing / expired
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
    # Return PNG directly from RAM
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

    print("\n========================================")
    print("           FABRIX")
    print("      VIRTUAL TRY ON SERVER")
    print("========================================")


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