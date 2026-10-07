// ============================================================
// FABRIX - CAMERA + MEDIAPIPE + GESTURES
//
// Handles:
// - MediaPipe Pose
// - MediaPipe Hands
// - Camera startup
// - Canvas sizing
// - Slider ranges
// - Two-hand pinch resize
// - One-hand pinch clothing drag
// - Camera-button index-finger capture trigger
//
// Capture UI / countdown logic:
//     try_on.js
//
// Sliders / mouse / touch / reset:
//     try_on_controls.js
//
// ============================================================


// ============================================================
// MEDIAPIPE POSE
// ============================================================

const pose =
    new Pose({

        locateFile:
            function (file) {

                return (
                    `https://cdn.jsdelivr.net/npm/@mediapipe/pose/${file}`
                );

            }

    });


pose.setOptions({

    modelComplexity: 1,

    smoothLandmarks: true,

    enableSegmentation: false,

    smoothSegmentation: false,

    minDetectionConfidence: 0.5,

    minTrackingConfidence: 0.5

});


pose.onResults(
    function (results) {

        poseResults =
            results;

        drawScene();

    }
);


// ============================================================
// MEDIAPIPE HANDS
// ============================================================

const hands =
    new Hands({

        locateFile:
            function (file) {

                return (
                    `https://cdn.jsdelivr.net/npm/@mediapipe/hands/${file}`
                );

            }

    });


hands.setOptions({

    maxNumHands: 2,

    modelComplexity: 1,

    minDetectionConfidence: 0.5,

    minTrackingConfidence: 0.5

});


hands.onResults(
    function (results) {

        handResults =
            results;


        // ====================================================
        // CAMERA BUTTON CAPTURE
        // ====================================================

        /*
         * Checks whether the user's index finger is pointing
         * at the virtual camera button.
         *
         * The function is defined in try_on.js.
         *
         * The user must keep the index finger over the
         * camera button for 2 seconds before the countdown
         * starts.
         */

        processCameraButtonCapture();


        // ====================================================
        // NORMAL CLOTHING GESTURES
        // ====================================================

        processHandGesture();


        // ====================================================
        // REDRAW
        // ====================================================

        drawScene();

    }
);


// ============================================================
// CAMERA
// ============================================================

let camera = null;


function startCamera() {

    try {

        camera =
            new Camera(
                video,
                {

                    onFrame:
                        async function () {

                            if (
                                !video.videoWidth ||
                                !video.videoHeight
                            ) {

                                return;

                            }


                            // ==================================
                            // POSE
                            // ==================================

                            await pose.send({

                                image: video

                            });


                            // ==================================
                            // HANDS
                            // ==================================

                            await hands.send({

                                image: video

                            });

                        },


                    width: 640,

                    height: 480

                }
            );


        camera.start();

    }
    catch (error) {

        console.error(
            "Camera error:",
            error
        );


        setStatus(
            "Unable to start camera."
        );

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


        updateSliderRanges();

        updateSliders();

    }

}


// ============================================================
// SLIDER RANGES
// ============================================================

function updateSliderRanges() {

    if (xSlider) {

        xSlider.min =
            0;

        xSlider.max =
            canvas.width;

    }


    if (ySlider) {

        ySlider.min =
            0;

        ySlider.max =
            canvas.height;

    }


    if (scaleSlider) {

        scaleSlider.min =
            MIN_CLOTHING_SCALE;

        scaleSlider.max =
            MAX_CLOTHING_SCALE;

    }

}


// ============================================================
// VIDEO EVENTS
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

function getHandPinchData(
    landmarks
) {

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
// TWO-HAND PINCH RESIZE
// ============================================================

function processTwoHandResize() {

    if (
        !handResults ||
        !handResults.multiHandLandmarks
    ) {

        resetTwoHandResize();

        return false;

    }


    const handsDetected =
        handResults.multiHandLandmarks;


    if (
        handsDetected.length < 2
    ) {

        resetTwoHandResize();

        return false;

    }


    const hand1 =
        getHandPinchData(
            handsDetected[0]
        );


    const hand2 =
        getHandPinchData(
            handsDetected[1]
        );


    if (
        !hand1 ||
        !hand2
    ) {

        resetTwoHandResize();

        return false;

    }


    if (
        !hand1.pinchDetected ||
        !hand2.pinchDetected
    ) {

        resetTwoHandResize();

        return false;

    }


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


    const dx =
        point2.x -
        point1.x;


    const dy =
        point2.y -
        point1.y;


    const currentDistance =
        Math.sqrt(

            dx * dx +
            dy * dy

        );


    if (
        previousTwoHandDistance === null
    ) {

        previousTwoHandDistance =
            currentDistance;


        twoHandResizeActive =
            true;


        setStatus(
            "🤏🤏 Two-hand resize active"
        );


        return true;

    }


    const distanceChange =
        currentDistance -
        previousTwoHandDistance;


    previousTwoHandDistance =
        currentDistance;


    if (
        Math.abs(
            distanceChange
        ) < 2
    ) {

        return true;

    }


    const scaleChange =
        (
            distanceChange /
            canvas.width
        ) *
        TWO_HAND_SCALE_SENSITIVITY;


    clothingScale +=
        scaleChange;


    clothingScale =
        Math.max(

            MIN_CLOTHING_SCALE,

            Math.min(

                MAX_CLOTHING_SCALE,

                clothingScale

            )

        );


    if (scaleSlider) {

        scaleSlider.value =
            clothingScale;

    }


    updateSliderLabels();


    if (
        distanceChange > 0
    ) {

        setStatus(
            "🤏🤏 Hands apart — clothing getting larger"
        );

    }
    else {

        setStatus(
            "🤏🤏 Hands closer — clothing getting smaller"
        );

    }


    return true;

}


// ============================================================
// RESET TWO-HAND RESIZE
// ============================================================

function resetTwoHandResize() {

    previousTwoHandDistance =
        null;


    if (
        twoHandResizeActive
    ) {

        twoHandResizeActive =
            false;

    }

}


// ============================================================
// HAND GESTURE PROCESSING
// ============================================================

function processHandGesture() {

    if (
        !handResults ||
        !handResults.multiHandLandmarks ||
        handResults.multiHandLandmarks.length === 0
    ) {

        resetTwoHandResize();


        if (isPinching) {

            isPinching =
                false;


            handDragging =
                false;


            saveManualOffset();


            setStatus(
                "Hand released"
            );

        }


        return;

    }


    const detectedHands =
        handResults.multiHandLandmarks;


    // ========================================================
    // TWO HANDS
    // ========================================================

    if (
        detectedHands.length >= 2
    ) {

        const resizeActive =
            processTwoHandResize();


        if (resizeActive) {

            if (isPinching) {

                isPinching =
                    false;

            }


            handDragging =
                false;


            return;

        }

    }
    else {

        resetTwoHandResize();

    }


    // ========================================================
    // ONE HAND
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


    const canvasPinchX =
        normalizedToCanvasX(
            pinchData.pinchX
        );


    const canvasPinchY =
        normalizedToCanvasY(
            pinchData.pinchY
        );


    const pinchDetected =
        pinchData.pinchDetected;


    // ========================================================
    // PINCH START
    // ========================================================

    if (
        pinchDetected &&
        !isPinching
    ) {

        if (
            isPointInsideClothing(
                canvasPinchX,
                canvasPinchY
            )
        ) {

            isPinching =
                true;


            handDragging =
                true;


            dragOffsetX =
                clothingX -
                canvasPinchX;


            dragOffsetY =
                clothingY -
                canvasPinchY;


            setStatus(
                "🤏 Clothing grabbed"
            );

        }

    }


    // ========================================================
    // CONTINUE DRAGGING
    // ========================================================

    if (
        pinchDetected &&
        isPinching &&
        handDragging
    ) {

        clothingX =
            canvasPinchX +
            dragOffsetX;


        clothingY =
            canvasPinchY +
            dragOffsetY;


        updateSliderLabels();

    }


    // ========================================================
    // PINCH RELEASE
    // ========================================================

    if (
        !pinchDetected &&
        isPinching
    ) {

        isPinching =
            false;


        handDragging =
            false;


        saveManualOffset();


        setStatus(
            "Clothing released"
        );

    }

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
// START CAMERA
// ============================================================
//
// IMPORTANT:
// This call was missing from the uploaded file.
//
// The function above only DEFINES startCamera().
// This actually starts MediaPipe + webcam processing.
// ============================================================

startCamera();