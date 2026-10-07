// ============================================================
// FABRIX - VIRTUAL TRY-ON
// CORE TRY-ON LOGIC
// ============================================================
//
// Handles:
//
// - Camera/canvas DOM
// - Clothing state
// - Pose-based clothing positioning
// - Clothing rendering
// - Manual offsets
// - Index-finger camera-button capture
// - 2-second pointing activation
// - 5-second capture countdown
// - Captured image display
// - Captured image download
// - Coordinate conversion
// - Clothing loading
//
// Camera / MediaPipe processing:
//     try_on_camera.js
//
// Sliders / mouse / touch / reset:
//     try_on_controls.js
//
// ============================================================


// ============================================================
// CAMERA CONFIGURATION
// ============================================================

const FORCE_NORMAL_CAMERA = true;


// ============================================================
// DOM ELEMENTS
// ============================================================

const video =
    document.getElementById("video");

const canvas =
    document.getElementById("output");

const ctx =
    canvas.getContext("2d");

const statusText =
    document.getElementById("status");

const xSlider =
    document.getElementById("xSlider");

const ySlider =
    document.getElementById("ySlider");

const scaleSlider =
    document.getElementById("scaleSlider");

const xValue =
    document.getElementById("xValue");

const yValue =
    document.getElementById("yValue");

const scaleValue =
    document.getElementById("scaleValue");

const resetBtn =
    document.getElementById("resetBtn");

const cameraLoading =
    document.getElementById("cameraLoading");


// ============================================================
// CAPTURE DOM ELEMENTS
// ============================================================

const cameraCaptureBtn =
    document.getElementById("cameraCaptureBtn");

const captureCountdown =
    document.getElementById("captureCountdown");

const capturedImageSection =
    document.getElementById("capturedImageSection");

const capturedImage =
    document.getElementById("capturedImage");

const downloadCapturedBtn =
    document.getElementById("downloadCapturedBtn");

// OLD "TAKE SNAPSHOT" BUTTON
// Kept for compatibility with the existing HTML.
const snapshotBtn =
    document.getElementById("snapshotBtn");


// ============================================================
// CLOTHING VARIABLES
// ============================================================

const clothingImage =
    new Image();

let clothingReady = false;
let clothingLoaded = false;
let cameraLoaded = false;
let clothingURL = null;

let clothingX = 0;
let clothingY = 0;
let clothingScale = 1;

let clothingWidth = 0;
let clothingHeight = 0;


// ============================================================
// AUTOMATIC POSE POSITION
// ============================================================

let autoClothingX = 0;
let autoClothingY = 0;


// ============================================================
// MANUAL POSITION OFFSET
// ============================================================

let manualOffsetX = 0;
let manualOffsetY = 0;


// ============================================================
// POSE VARIABLES
// ============================================================

let poseResults = null;


// ============================================================
// HAND VARIABLES
// ============================================================

let handResults = null;

let isPinching = false;
let handDragging = false;


// ============================================================
// CAPTURE VARIABLES
// ============================================================

let capturePointStartTime = null;
let captureActive = false;
let captureCountdownTimer = null;
let capturedImageData = null;

// User must point at the camera button for 2 seconds.
const CAMERA_BUTTON_HOLD_TIME = 2000;

// Countdown duration.
const CAPTURE_COUNTDOWN_TIME = 5000;


// ============================================================
// CAMERA BUTTON DETECTION
// ============================================================

// Prevent the camera button from triggering continuously
// while the countdown is running.
let cameraButtonPointing = false;


// ============================================================
// PINCH CONFIGURATION
// ============================================================

const PINCH_THRESHOLD = 0.055;
const GRAB_PADDING = 40;


// ============================================================
// HAND DRAG OFFSET
// ============================================================

let dragOffsetX = 0;
let dragOffsetY = 0;


// ============================================================
// TWO-HAND PINCH RESIZE
// ============================================================

let twoHandResizeActive = false;
let previousTwoHandDistance = null;

const TWO_HAND_SCALE_SENSITIVITY = 1.8;

const MIN_CLOTHING_SCALE = 0.50;
const MAX_CLOTHING_SCALE = 2.00;


// ============================================================
// MOUSE / TOUCH VARIABLES
// ============================================================

let mouseDragging = false;
let mouseOffsetX = 0;
let mouseOffsetY = 0;


// ============================================================
// STATUS
// ============================================================

function setStatus(message) {

    if (statusText) {
        statusText.textContent = message;
    }
}


// ============================================================
// CAMERA LOADING
// ============================================================

function hideCameraLoading() {

    if (cameraLoading) {
        cameraLoading.classList.add("hidden");
    }
}


function showCameraLoading() {

    if (cameraLoading) {
        cameraLoading.classList.remove("hidden");
    }
}


// ============================================================
// COORDINATE CONVERSION
// ============================================================

function normalizedToCanvasX(normalizedX) {

    if (FORCE_NORMAL_CAMERA) {

        return (
            1 - normalizedX
        ) * canvas.width;
    }

    return (
        normalizedX *
        canvas.width
    );
}


function normalizedToCanvasY(normalizedY) {

    return (
        normalizedY *
        canvas.height
    );
}


function normalizedToCanvasPoint(point) {

    return {

        x:
            normalizedToCanvasX(
                point.x
            ),

        y:
            normalizedToCanvasY(
                point.y
            )
    };
}


// ============================================================
// AUTOMATIC SCROLL TO CAMERA
// ============================================================

function scrollToCamera() {

    const cameraCard =
        document.querySelector(
            ".camera-card"
        );

    if (!cameraCard) {
        return;
    }

    setTimeout(() => {

        cameraCard.scrollIntoView({
            behavior: "smooth",
            block: "start"
        });

    }, 300);
}


// ============================================================
// CAPTURED IMAGE SECTION
// ============================================================

function showCapturedImage(imageData) {

    if (!capturedImageSection) {
        return;
    }

    if (capturedImage) {
        capturedImage.src = imageData;
    }

    capturedImageSection.hidden = false;

    if (downloadCapturedBtn) {
        downloadCapturedBtn.disabled = false;
    }

    setTimeout(() => {

        capturedImageSection.scrollIntoView({
            behavior: "smooth",
            block: "start"
        });

    }, 300);
}


// ============================================================
// CAPTURE IMAGE
// ============================================================

function captureTryOnImage() {

    if (
        !canvas ||
        !canvas.width ||
        !canvas.height
    ) {
        setStatus("Camera is not ready.");
        return;
    }

    // Draw the latest camera frame and clothing
    // before taking the picture.
    drawScene();

    const imageData =
        canvas.toDataURL(
            "image/png"
        );

    capturedImageData =
        imageData;

    showCapturedImage(
        imageData
    );
}


// ============================================================
// DOWNLOAD CAPTURED IMAGE
// ============================================================

function downloadCapturedImage() {

    if (!capturedImageData) {

        setStatus(
            "No captured image available."
        );

        return;
    }

    const link =
        document.createElement("a");

    link.download =
        "fabrix-try-on.png";

    link.href =
        capturedImageData;

    document.body.appendChild(link);

    link.click();

    document.body.removeChild(link);
}


// ============================================================
// DOWNLOAD BUTTON
// ============================================================

if (downloadCapturedBtn) {

    downloadCapturedBtn.addEventListener(
        "click",
        function () {

            downloadCapturedImage();

        }
    );

}


// ============================================================
// CAMERA BUTTON UI
// ============================================================

function showCameraButton() {

    if (!cameraCaptureBtn) {
        return;
    }

    cameraCaptureBtn.classList.remove(
        "capture-active"
    );

    cameraCaptureBtn.classList.remove(
        "pointing"
    );

    cameraCaptureBtn.style.display =
        "flex";
}


function hideCameraButton() {

    if (!cameraCaptureBtn) {
        return;
    }

    cameraCaptureBtn.classList.add(
        "capture-active"
    );
}


// ============================================================
// CAMERA BUTTON POINTING STATE
// ============================================================

function setCameraButtonPointing(pointing) {

    if (!cameraCaptureBtn) {
        return;
    }

    cameraButtonPointing =
        pointing;

    if (pointing) {

        cameraCaptureBtn.classList.add(
            "pointing"
        );

    }
    else {

        cameraCaptureBtn.classList.remove(
            "pointing"
        );

    }
}


// ============================================================
// GET INDEX FINGER POSITION
// ============================================================

// MediaPipe landmark 8 = index fingertip.

function getIndexFingerPoint(landmarks) {

    if (
        !landmarks ||
        landmarks.length < 21
    ) {
        return null;
    }

    const indexTip =
        landmarks[8];

    if (!indexTip) {
        return null;
    }

    return normalizedToCanvasPoint({
        x: indexTip.x,
        y: indexTip.y
    });
}


// ============================================================
// CHECK INDEX FINGER IS EXTENDED
// ============================================================

function isIndexFingerPointing(landmarks) {

    if (
        !landmarks ||
        landmarks.length < 21
    ) {
        return false;
    }

    const indexTip =
        landmarks[8];

    const indexPIP =
        landmarks[6];

    const indexMCP =
        landmarks[5];

    const middleTip =
        landmarks[12];

    const middlePIP =
        landmarks[10];

    const ringTip =
        landmarks[16];

    const ringPIP =
        landmarks[14];

    const pinkyTip =
        landmarks[20];

    const pinkyPIP =
        landmarks[18];

    if (
        !indexTip ||
        !indexPIP ||
        !indexMCP
    ) {
        return false;
    }

    // Index finger should be extended.
    const indexExtended =
        Math.abs(
            indexTip.y -
            indexMCP.y
        ) >
        Math.abs(
            indexPIP.y -
            indexMCP.y
        );

    // Other fingers should preferably be folded.
    const middleFolded =
        middleTip.y >
        middlePIP.y;

    const ringFolded =
        ringTip.y >
        ringPIP.y;

    const pinkyFolded =
        pinkyTip.y >
        pinkyPIP.y;

    return (
        indexExtended &&
        middleFolded &&
        ringFolded &&
        pinkyFolded
    );
}


// ============================================================
// CHECK INDEX FINGER IS OVER CAMERA BUTTON
// ============================================================

function isIndexOverCameraButton(landmarks) {

    if (
        !cameraCaptureBtn ||
        !canvas
    ) {
        return false;
    }

    if (
        !isIndexFingerPointing(
            landmarks
        )
    ) {
        return false;
    }

    const indexPoint =
        getIndexFingerPoint(
            landmarks
        );

    if (!indexPoint) {
        return false;
    }

    // Convert canvas coordinates to
    // actual screen coordinates.
    const canvasRect =
        canvas.getBoundingClientRect();

    const canvasScaleX =
        canvasRect.width /
        canvas.width;

    const canvasScaleY =
        canvasRect.height /
        canvas.height;

    const screenX =
        canvasRect.left +
        (
            indexPoint.x *
            canvasScaleX
        );

    const screenY =
        canvasRect.top +
        (
            indexPoint.y *
            canvasScaleY
        );

    const buttonRect =
        cameraCaptureBtn.getBoundingClientRect();

    // Add a small tolerance around the button
    // so the user does not have to be perfectly precise.
    const tolerance = 25;

    return (
        screenX >=
            buttonRect.left -
            tolerance &&

        screenX <=
            buttonRect.right +
            tolerance &&

        screenY >=
            buttonRect.top -
            tolerance &&

        screenY <=
            buttonRect.bottom +
            tolerance
    );
}


// ============================================================
// PROCESS CAMERA BUTTON POINTING
// ============================================================

function processCameraButtonCapture() {

    // Do nothing while countdown is running.
    if (captureActive) {
        return;
    }

    if (
        !handResults ||
        !handResults.multiHandLandmarks ||
        handResults.multiHandLandmarks.length === 0
    ) {

        cancelCameraButtonPointing();

        return;
    }

    // Only use the first detected hand
    // for camera-button pointing.
    const landmarks =
        handResults.multiHandLandmarks[0];

    const pointing =
        isIndexOverCameraButton(
            landmarks
        );

    if (!pointing) {

        cancelCameraButtonPointing();

        return;
    }

    setCameraButtonPointing(true);

    if (
        capturePointStartTime === null
    ) {

        capturePointStartTime =
            Date.now();

        setStatus(
            "☝️ Keep your finger on the camera button..."
        );

        return;
    }

    const heldTime =
        Date.now() -
        capturePointStartTime;

    if (
        heldTime >=
        CAMERA_BUTTON_HOLD_TIME
    ) {

        startCaptureCountdown();

    }
}


// ============================================================
// CANCEL CAMERA BUTTON POINTING
// ============================================================

function cancelCameraButtonPointing() {

    if (captureActive) {
        return;
    }

    capturePointStartTime =
        null;

    setCameraButtonPointing(
        false
    );
}


// ============================================================
// START 5-SECOND COUNTDOWN
// ============================================================

function startCaptureCountdown() {

    if (captureActive) {
        return;
    }

    captureActive = true;

    capturePointStartTime =
        null;

    setCameraButtonPointing(
        false
    );

    hideCameraButton();

    let remainingSeconds =
        Math.ceil(
            CAPTURE_COUNTDOWN_TIME /
            1000
        );

    showCountdownNumber(
        remainingSeconds
    );

    setStatus(
        `📸 Capturing in ${remainingSeconds}...`
    );

    captureCountdownTimer =
        setInterval(
            function () {

                remainingSeconds--;

                if (
                    remainingSeconds > 0
                ) {

                    showCountdownNumber(
                        remainingSeconds
                    );

                    setStatus(
                        `📸 Capturing in ${remainingSeconds}...`
                    );

                }
                else {

                    clearInterval(
                        captureCountdownTimer
                    );

                    captureCountdownTimer =
                        null;

                    hideCountdown();

                    captureTryOnImage();

                    setStatus(
                        "📸 Image captured!"
                    );

                    // Bring the camera button back
                    // after the capture.
                    setTimeout(
                        function () {

                            captureActive =
                                false;

                            showCameraButton();

                            setStatus(
                                "Camera ready — point at 📷 for 2 seconds to capture again."
                            );

                        },
                        1000
                    );
                }

            },
            1000
        );
}


// ============================================================
// SHOW COUNTDOWN NUMBER
// ============================================================

function showCountdownNumber(number) {

    if (!captureCountdown) {
        return;
    }

    captureCountdown.textContent =
        number;

    captureCountdown.classList.remove(
        "visible"
    );

    // Force browser reflow so the
    // animation starts again.
    void captureCountdown.offsetWidth;

    captureCountdown.classList.add(
        "visible"
    );
}


// ============================================================
// HIDE COUNTDOWN
// ============================================================

function hideCountdown() {

    if (!captureCountdown) {
        return;
    }

    captureCountdown.classList.remove(
        "visible"
    );
}


// ============================================================
// CAMERA BUTTON MANUAL CLICK
// ============================================================

// This is useful as a fallback for desktop users.
// The gesture system remains the main interaction.

if (cameraCaptureBtn) {

    cameraCaptureBtn.addEventListener(
        "click",
        function () {

            if (captureActive) {
                return;
            }

            startCaptureCountdown();

        }
    );

}


// ============================================================
// OLD "TAKE SNAPSHOT" BUTTON
// ============================================================
//
// This connects the old HTML button:
//
//     <button id="snapshotBtn">
//         Take Snapshot
//     </button>
//
// It uses the same 5-second countdown as the
// camera button, so both capture methods behave
// consistently.
//
// ============================================================

if (snapshotBtn) {

    snapshotBtn.addEventListener(
        "click",
        function () {

            if (captureActive) {
                return;
            }

            startCaptureCountdown();

        }
    );

}


// ============================================================
// LOAD CLOTHING FROM URL
// ============================================================

function loadClothingFromURL() {

    const params =
        new URLSearchParams(
            window.location.search
        );

    const clothingSource =
        params.get("clothing");

    if (!clothingSource) {

        clothingReady = false;

        setStatus(
            "No clothing image was selected."
        );

        return;
    }

    setStatus(
        "Loading clothing..."
    );

    clothingReady = false;
    clothingLoaded = false;

    clothingImage.onload =
        function () {

            clothingLoaded =
                true;

            if (cameraLoaded) {
                scrollToCamera();
            }

            clothingReady =
                true;

            // Reset interaction state.
            isPinching =
                false;

            handDragging =
                false;

            mouseDragging =
                false;

            twoHandResizeActive =
                false;

            previousTwoHandDistance =
                null;

            // Reset clothing scale.
            clothingScale =
                1;

            // Reset manual position.
            manualOffsetX =
                0;

            manualOffsetY =
                0;

            if (
                canvas.width > 0 &&
                canvas.height > 0
            ) {

                clothingX =
                    canvas.width / 2;

                clothingY =
                    canvas.height / 2;
            }

            // updateSliders() is defined in this
            // file and is therefore safe to call.
            updateSliders();

            drawScene();

            setStatus(
                "Clothing loaded successfully"
            );
        };

    clothingImage.onerror =
        function () {

            clothingReady =
                false;

            clothingLoaded =
                false;

            setStatus(
                "Unable to load clothing image."
            );
        };

    // Do not revoke this URL.
    // It may be a server URL.
    clothingURL =
        clothingSource;

    clothingImage.src =
        clothingSource;
}


// ============================================================
// DRAW SCENE
// ============================================================

function drawScene() {

    if (
        !video.videoWidth ||
        !video.videoHeight
    ) {
        return;
    }

    if (
        canvas.width !== video.videoWidth ||
        canvas.height !== video.videoHeight
    ) {

        canvas.width =
            video.videoWidth;

        canvas.height =
            video.videoHeight;

        // Do not call updateSliderRanges()
        // because that function belongs to
        // the controls file.

        updateSliders();
    }

    ctx.clearRect(
        0,
        0,
        canvas.width,
        canvas.height
    );


    // ========================================================
    // CAMERA
    // ========================================================

    if (FORCE_NORMAL_CAMERA) {

        ctx.save();

        ctx.translate(
            canvas.width,
            0
        );

        ctx.scale(
            -1,
            1
        );

        ctx.drawImage(
            video,
            0,
            0,
            canvas.width,
            canvas.height
        );

        ctx.restore();
    }
    else {

        ctx.drawImage(
            video,
            0,
            0,
            canvas.width,
            canvas.height
        );
    }


    // ========================================================
    // CLOTHING
    // ========================================================

    if (clothingReady) {

        calculateClothingSize();

        drawClothing();
    }


    // ========================================================
    // HAND CURSORS
    // ========================================================

    drawFingerCursor();
}


// ============================================================
// CALCULATE CLOTHING SIZE AND POSITION
// ============================================================

function calculateClothingSize() {

    if (
        !poseResults ||
        !poseResults.poseLandmarks
    ) {
        return;
    }

    const landmarks =
        poseResults.poseLandmarks;

    const leftShoulder =
        landmarks[11];

    const rightShoulder =
        landmarks[12];

    const leftHip =
        landmarks[23];

    const rightHip =
        landmarks[24];

    if (
        !leftShoulder ||
        !rightShoulder ||
        !leftHip ||
        !rightHip
    ) {
        return;
    }


    // ========================================================
    // SHOULDER DISTANCE
    // ========================================================

    const shoulderDX =
        rightShoulder.x -
        leftShoulder.x;

    const shoulderDY =
        rightShoulder.y -
        leftShoulder.y;

    const shoulderDistance =
        Math.sqrt(
            shoulderDX * shoulderDX +
            shoulderDY * shoulderDY
        );

    const shoulderWidth =
        shoulderDistance *
        canvas.width;


    // ========================================================
    // AUTOMATIC CLOTHING SIZE
    // ========================================================

    clothingWidth =
        shoulderWidth *
        1.45 *
        clothingScale;

    if (
        clothingImage.naturalWidth > 0 &&
        clothingImage.naturalHeight > 0
    ) {

        clothingHeight =
            clothingWidth *
            (
                clothingImage.naturalHeight /
                clothingImage.naturalWidth
            );
    }


    // ========================================================
    // AUTOMATIC BODY POSITION
    // ========================================================

    const centerX =
        (
            leftShoulder.x +
            rightShoulder.x
        ) / 2;

    const centerY =
        (
            leftShoulder.y +
            rightShoulder.y
        ) / 2;

    autoClothingX =
        normalizedToCanvasX(
            centerX
        );

    autoClothingY =
        (
            centerY *
            canvas.height
        ) +
        clothingHeight * 0.35;


    // ========================================================
    // APPLY MANUAL OFFSET
    // ========================================================

    if (
        !handDragging &&
        !mouseDragging
    ) {

        clothingX =
            autoClothingX +
            manualOffsetX;

        clothingY =
            autoClothingY +
            manualOffsetY;
    }
}


// ============================================================
// DRAW CLOTHING
// ============================================================

function drawClothing() {

    if (!clothingReady) {
        return;
    }

    if (
        clothingWidth <= 0 ||
        clothingHeight <= 0
    ) {
        return;
    }

    const drawX =
        clothingX -
        clothingWidth / 2;

    const drawY =
        clothingY -
        clothingHeight / 2;

    ctx.save();

    ctx.globalAlpha =
        0.96;

    ctx.drawImage(
        clothingImage,
        drawX,
        drawY,
        clothingWidth,
        clothingHeight
    );

    ctx.restore();


    // Show clothing boundary while dragging.
    if (
        handDragging ||
        mouseDragging
    ) {

        ctx.save();

        ctx.strokeStyle =
            "#ff6b35";

        ctx.lineWidth =
            3;

        ctx.setLineDash([
            8,
            6
        ]);

        ctx.strokeRect(
            drawX,
            drawY,
            clothingWidth,
            clothingHeight
        );

        ctx.restore();
    }
}


// ============================================================
// DISTANCE BETWEEN TWO POINTS
// ============================================================

function normalizedDistance(
    pointA,
    pointB
) {

    if (
        !pointA ||
        !pointB
    ) {
        return 0;
    }

    const dx =
        pointA.x -
        pointB.x;

    const dy =
        pointA.y -
        pointB.y;

    return Math.sqrt(
        dx * dx +
        dy * dy
    );
}


// ============================================================
// GET PINCH POINT
// ============================================================

function getHandPinchData(landmarks) {

    if (!landmarks) {
        return null;
    }

    const thumbTip =
        landmarks[4];

    const indexTip =
        landmarks[8];

    if (
        !thumbTip ||
        !indexTip
    ) {
        return null;
    }

    const distance =
        normalizedDistance(
            thumbTip,
            indexTip
        );

    const pinchDetected =
        distance <
        PINCH_THRESHOLD;

    const pinchX =
        (
            thumbTip.x +
            indexTip.x
        ) / 2;

    const pinchY =
        (
            thumbTip.y +
            indexTip.y
        ) / 2;

    return {
        thumbTip,
        indexTip,
        distance,
        pinchDetected,
        pinchX,
        pinchY
    };
}


// ============================================================
// SAVE MANUAL POSITION AS OFFSET
// ============================================================

function saveManualOffset() {

    manualOffsetX =
        clothingX -
        autoClothingX;

    manualOffsetY =
        clothingY -
        autoClothingY;
}


// ============================================================
// CHECK WHETHER POINT IS INSIDE CLOTHING
// ============================================================

function isPointInsideClothing(
    x,
    y
) {

    if (!clothingReady) {
        return false;
    }

    const left =
        clothingX -
        clothingWidth / 2 -
        GRAB_PADDING;

    const right =
        clothingX +
        clothingWidth / 2 +
        GRAB_PADDING;

    const top =
        clothingY -
        clothingHeight / 2 -
        GRAB_PADDING;

    const bottom =
        clothingY +
        clothingHeight / 2 +
        GRAB_PADDING;

    return (
        x >= left &&
        x <= right &&
        y >= top &&
        y <= bottom
    );
}


// ============================================================
// DRAW HAND / PINCH CURSOR
// ============================================================

function drawFingerCursor() {

    if (
        !handResults ||
        !handResults.multiHandLandmarks ||
        handResults.multiHandLandmarks.length === 0
    ) {
        return;
    }

    const detectedHands =
        handResults.multiHandLandmarks;


    // ========================================================
    // TWO-HAND DISPLAY
    // ========================================================

    if (
        detectedHands.length >= 2
    ) {

        const hand1 =
            getHandPinchData(
                detectedHands[0]
            );

        const hand2 =
            getHandPinchData(
                detectedHands[1]
            );

        if (
            hand1 &&
            hand2
        ) {

            const point1 =
                normalizedToCanvasPoint({
                    x: hand1.pinchX,
                    y: hand1.pinchY
                });

            const point2 =
                normalizedToCanvasPoint({
                    x: hand2.pinchX,
                    y: hand2.pinchY
                });

            drawPinchPoint(
                point1.x,
                point1.y,
                hand1.pinchDetected
            );

            drawPinchPoint(
                point2.x,
                point2.y,
                hand2.pinchDetected
            );

            if (
                hand1.pinchDetected &&
                hand2.pinchDetected
            ) {

                ctx.save();

                ctx.beginPath();

                ctx.moveTo(
                    point1.x,
                    point1.y
                );

                ctx.lineTo(
                    point2.x,
                    point2.y
                );

                ctx.strokeStyle =
                    "#ff6b35";

                ctx.lineWidth =
                    4;

                ctx.setLineDash([
                    10,
                    6
                ]);

                ctx.stroke();

                ctx.restore();
            }
        }

        return;
    }


    // ========================================================
    // ONE-HAND DISPLAY
    // ========================================================

    const landmarks =
        detectedHands[0];

    const pinchData =
        getHandPinchData(
            landmarks
        );

    if (!pinchData) {
        return;
    }

    const point =
        normalizedToCanvasPoint({
            x: pinchData.pinchX,
            y: pinchData.pinchY
        });

    drawPinchPoint(
        point.x,
        point.y,
        pinchData.pinchDetected
    );

    if (
        pinchData.pinchDetected
    ) {

        const thumbPoint =
            normalizedToCanvasPoint(
                pinchData.thumbTip
            );

        const indexPoint =
            normalizedToCanvasPoint(
                pinchData.indexTip
            );

        ctx.save();

        ctx.beginPath();

        ctx.moveTo(
            thumbPoint.x,
            thumbPoint.y
        );

        ctx.lineTo(
            indexPoint.x,
            indexPoint.y
        );

        ctx.strokeStyle =
            "#ff6b35";

        ctx.lineWidth =
            4;

        ctx.stroke();

        ctx.restore();
    }
}


// ============================================================
// DRAW PINCH POINT
// ============================================================

function drawPinchPoint(
    x,
    y,
    pinching
) {

    ctx.save();

    ctx.beginPath();

    ctx.arc(
        x,
        y,
        pinching
            ? 13
            : 8,
        0,
        Math.PI * 2
    );

    ctx.fillStyle =
        pinching
            ? "#ff6b35"
            : "#ffffff";

    ctx.fill();

    ctx.lineWidth =
        3;

    ctx.strokeStyle =
        "#111111";

    ctx.stroke();

    ctx.restore();
}


// ============================================================
// SLIDER VALUES
// ============================================================

function updateSliders() {

    if (xSlider) {

        xSlider.value =
            Math.round(
                clothingX
            );
    }

    if (ySlider) {

        ySlider.value =
            Math.round(
                clothingY
            );
    }

    if (scaleSlider) {

        scaleSlider.value =
            clothingScale;
    }

    updateSliderLabels();
}


function updateSliderLabels() {

    if (xValue) {

        xValue.textContent =
            Math.round(
                clothingX
            );
    }

    if (yValue) {

        yValue.textContent =
            Math.round(
                clothingY
            );
    }

    if (scaleValue) {

        scaleValue.textContent =
            clothingScale.toFixed(2);
    }
}


// ============================================================
// CANVAS SIZE
// ============================================================

function resizeCanvas() {

    if (
        !video.videoWidth ||
        !video.videoHeight
    ) {
        return;
    }

    if (
        canvas.width !== video.videoWidth ||
        canvas.height !== video.videoHeight
    ) {

        canvas.width =
            video.videoWidth;

        canvas.height =
            video.videoHeight;

        // Do not call updateSliderRanges()
        // because that function belongs to
        // the controls file.

        updateSliders();
    }
}


// ============================================================
// INITIAL CAMERA / VIDEO EVENTS
// ============================================================

video.addEventListener(
    "loadedmetadata",
    function () {

        resizeCanvas();

        drawScene();

    }
);


video.addEventListener(
    "playing",
    function () {

        cameraLoaded =
            true;

        if (clothingLoaded) {
            scrollToCamera();
        }

        hideCameraLoading();

        setStatus(
            clothingReady
                ? "Camera ready — point your index finger at 📷 for 2 seconds."
                : "Loading clothing..."
        );

    }
);


// ============================================================
// WINDOW RESIZE
// ============================================================

window.addEventListener(
    "resize",
    function () {

        resizeCanvas();

        drawScene();

    }
);


// ============================================================
// PAGE VISIBILITY
// ============================================================

document.addEventListener(
    "visibilitychange",
    function () {

        if (!document.hidden) {

            resizeCanvas();

            drawScene();

        }

    }
);


// ============================================================
// RESET CAPTURE STATE
// ============================================================

function resetCaptureState() {

    if (
        captureCountdownTimer !== null
    ) {

        clearInterval(
            captureCountdownTimer
        );

        captureCountdownTimer =
            null;
    }

    capturePointStartTime =
        null;

    captureActive =
        false;

    cameraButtonPointing =
        false;

    capturedImageData =
        null;

    if (capturedImageSection) {
        capturedImageSection.hidden = true;
    }

    if (capturedImage) {
        capturedImage.src = "";
    }

    if (downloadCapturedBtn) {
        downloadCapturedBtn.disabled = true;
    }

    hideCountdown();

    showCameraButton();
}


// ============================================================
// RESET BUTTON CAPTURE STATE
// ============================================================

if (resetBtn) {

    resetBtn.addEventListener(
        "click",
        function () {

            resetCaptureState();

        }
    );

}


// ============================================================
// CAMERA ERROR HANDLING
// ============================================================

window.addEventListener(
    "error",
    function (event) {

        console.error(
            "Fabrix error:",
            event.error ||
            event.message
        );

    }
);


// ============================================================
// INITIALIZATION
// ============================================================

showCameraLoading();

setStatus(
    "Loading clothing and starting camera..."
);

// Do NOT call updateSliderRanges() here.
// That function belongs to try_on_controls.js.

// Do NOT call updateSliderLabels() here.
// The controls file handles slider initialization.

// Load clothing selected
// on the previous page.
loadClothingFromURL();

// Make sure the camera button
// starts visible.
showCameraButton();