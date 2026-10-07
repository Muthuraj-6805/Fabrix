// ============================================================
// FABRIX - CONTROLS
//
// Handles:
// - X / Y / Scale sliders
// - Mouse clothing drag
// - Touch clothing drag
// - Reset
// - Page visibility
// - Error handling
//
// Camera capture / countdown:
//     try_on.js
//
// MediaPipe / camera:
//     try_on_camera.js
//
// ============================================================


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


// ============================================================
// SLIDER LABELS
// ============================================================

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
// X SLIDER
// ============================================================

if (xSlider) {

    xSlider.addEventListener(
        "input",
        function () {

            clothingX =
                Number(
                    xSlider.value
                );


            // Store the slider adjustment
            // relative to the person's body.

            manualOffsetX =
                clothingX -
                autoClothingX;


            updateSliderLabels();

            drawScene();

        }
    );

}


// ============================================================
// Y SLIDER
// ============================================================

if (ySlider) {

    ySlider.addEventListener(
        "input",
        function () {

            clothingY =
                Number(
                    ySlider.value
                );


            // Store the slider adjustment
            // relative to the person's body.

            manualOffsetY =
                clothingY -
                autoClothingY;


            updateSliderLabels();

            drawScene();

        }
    );

}


// ============================================================
// SCALE SLIDER
// ============================================================

if (scaleSlider) {

    scaleSlider.addEventListener(
        "input",
        function () {

            clothingScale =
                Number(
                    scaleSlider.value
                );


            // Position tracking remains active.
            // Only the clothing size changes.

            updateSliderLabels();

            drawScene();

        }
    );

}


// ============================================================
// GET CANVAS COORDINATES
// ============================================================

function getCanvasCoordinates(
    clientX,
    clientY
) {

    const rect =
        canvas.getBoundingClientRect();


    /*
     * IMPORTANT:
     *
     * Do NOT horizontally flip mouse coordinates.
     *
     * The canvas already displays the normal
     * camera view.
     */

    const x =
        (
            clientX -
            rect.left
        ) *
        canvas.width /
        rect.width;


    const y =
        (
            clientY -
            rect.top
        ) *
        canvas.height /
        rect.height;


    return {

        x: x,

        y: y

    };

}


// ============================================================
// MOUSE DOWN
// ============================================================

canvas.addEventListener(
    "mousedown",
    function (event) {

        const point =
            getCanvasCoordinates(
                event.clientX,
                event.clientY
            );


        if (
            isPointInsideClothing(
                point.x,
                point.y
            )
        ) {

            mouseDragging =
                true;


            mouseOffsetX =
                clothingX -
                point.x;


            mouseOffsetY =
                clothingY -
                point.y;


            setStatus(
                "Clothing grabbed"
            );

        }

    }
);


// ============================================================
// MOUSE MOVE
// ============================================================

canvas.addEventListener(
    "mousemove",
    function (event) {

        if (!mouseDragging) {

            return;

        }


        const point =
            getCanvasCoordinates(
                event.clientX,
                event.clientY
            );


        clothingX =
            point.x +
            mouseOffsetX;


        clothingY =
            point.y +
            mouseOffsetY;


        updateSliderLabels();

        drawScene();

    }
);


// ============================================================
// MOUSE UP
// ============================================================

window.addEventListener(
    "mouseup",
    function () {

        if (mouseDragging) {

            mouseDragging =
                false;


            // Save the final manual position as
            // an offset from the person's body.

            saveManualOffset();


            setStatus(
                "Clothing released"
            );

        }

    }
);


// ============================================================
// TOUCH START
// ============================================================

canvas.addEventListener(
    "touchstart",
    function (event) {

        if (
            event.touches.length !== 1
        ) {

            return;

        }


        const touch =
            event.touches[0];


        const point =
            getCanvasCoordinates(
                touch.clientX,
                touch.clientY
            );


        if (
            isPointInsideClothing(
                point.x,
                point.y
            )
        ) {

            mouseDragging =
                true;


            mouseOffsetX =
                clothingX -
                point.x;


            mouseOffsetY =
                clothingY -
                point.y;


            setStatus(
                "Clothing grabbed"
            );

        }

    },
    {
        passive: false
    }
);


// ============================================================
// TOUCH MOVE
// ============================================================

canvas.addEventListener(
    "touchmove",
    function (event) {

        if (!mouseDragging) {

            return;

        }


        if (
            event.touches.length !== 1
        ) {

            return;

        }


        event.preventDefault();


        const touch =
            event.touches[0];


        const point =
            getCanvasCoordinates(
                touch.clientX,
                touch.clientY
            );


        clothingX =
            point.x +
            mouseOffsetX;


        clothingY =
            point.y +
            mouseOffsetY;


        updateSliderLabels();

        drawScene();

    },
    {
        passive: false
    }
);


// ============================================================
// TOUCH END
// ============================================================

canvas.addEventListener(
    "touchend",
    function () {

        if (mouseDragging) {

            mouseDragging =
                false;


            saveManualOffset();


            setStatus(
                "Clothing released"
            );

        }

    }
);


// ============================================================
// TOUCH CANCEL
// ============================================================

canvas.addEventListener(
    "touchcancel",
    function () {

        if (mouseDragging) {

            mouseDragging =
                false;


            saveManualOffset();

        }

    }
);


// ============================================================
// RESET
// ============================================================

if (resetBtn) {

    resetBtn.addEventListener(
        "click",
        function () {

            // ================================================
            // STOP ACTIVE CLOTHING GESTURES
            // ================================================

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


            // ================================================
            // REMOVE MANUAL POSITION ADJUSTMENT
            // ================================================

            manualOffsetX =
                0;


            manualOffsetY =
                0;


            // ================================================
            // RESET SCALE
            // ================================================

            clothingScale =
                1;


            // ================================================
            // RESTORE AUTOMATIC CLOTHING POSITION
            // ================================================

            if (
                poseResults &&
                poseResults.poseLandmarks
            ) {

                calculateClothingSize();

            }
            else if (
                canvas.width &&
                canvas.height
            ) {

                clothingX =
                    canvas.width / 2;


                clothingY =
                    canvas.height / 2;

            }


            // ================================================
            // UPDATE UI
            // ================================================

            updateSliders();


            // ================================================
            // RESET CAMERA CAPTURE
            // ================================================
            //
            // resetCaptureState() is defined in try_on.js.
            //
            // It:
            // - cancels the 2-second pointing timer
            // - cancels the countdown
            // - restores the camera button
            // - removes the captured image
            //
            // The typeof check prevents an error if the
            // function is unavailable for any reason.
            // ================================================

            if (
                typeof resetCaptureState ===
                "function"
            ) {

                resetCaptureState();

            }


            setStatus(
                "Clothing and capture reset"
            );


            drawScene();

        }
    );

}


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
//
// IMPORTANT:
//
// Camera initialization is intentionally NOT done here.
//
// try_on_camera.js owns:
//     startCamera()
//
// try_on.js owns:
//     loadClothingFromURL()
//
// This prevents duplicate initialization and duplicate
// camera/MediaPipe processing.
// ============================================================
