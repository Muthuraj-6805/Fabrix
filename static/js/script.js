/* =========================================================
   FABRIX - MAIN PAGE SCRIPT
   ========================================================= */


/* =========================================================
   ELEMENTS
   ========================================================= */

const dropZone =
    document.getElementById("dropZone");


const browseButton =
    document.getElementById("browseButton");


const fileInput =
    document.getElementById("fileInput");


const previewSection =
    document.getElementById("previewSection");


const originalImage =
    document.getElementById("originalImage");


const resultImage =
    document.getElementById("resultImage");


const processButton =
    document.getElementById("processButton");


const downloadButton =
    document.getElementById("downloadButton");


const tryOnButton =
    document.getElementById("tryOnButton");


const status =
    document.getElementById("status");


const clothesGrid =
    document.getElementById("clothesGrid");


const clothesSection =
    document.getElementById("clothesSection");


/* =========================================================
   STATE
   ========================================================= */

let selectedFile = null;

let resultURL = null;

let selectedClothing = null;


/*
    URL of the processed image stored temporarily
    in Flask server RAM.
*/

let processedClothingURL = null;


/* =========================================================
   OPEN FILE SELECTOR
   ========================================================= */

if (browseButton) {

    browseButton.addEventListener(
        "click",
        function (event) {

            event.stopPropagation();

            fileInput.click();

        }
    );

}


/* =========================================================
   FILE INPUT
   ========================================================= */

if (fileInput) {

    fileInput.addEventListener(
        "change",
        function () {

            if (
                this.files &&
                this.files.length > 0
            ) {

                handleFile(
                    this.files[0]
                );

            }

        }
    );

}


/* =========================================================
   DROP ZONE CLICK
   ========================================================= */

if (dropZone) {

    dropZone.addEventListener(
        "click",
        function (event) {

            if (
                event.target === browseButton
            ) {

                return;

            }


            fileInput.click();

        }
    );

}


/* =========================================================
   DRAG ENTER
   ========================================================= */

if (dropZone) {

    dropZone.addEventListener(
        "dragenter",
        function (event) {

            event.preventDefault();

            dropZone.classList.add(
                "dragging"
            );

        }
    );

}


/* =========================================================
   DRAG OVER
   ========================================================= */

if (dropZone) {

    dropZone.addEventListener(
        "dragover",
        function (event) {

            event.preventDefault();

            dropZone.classList.add(
                "dragging"
            );

        }
    );

}


/* =========================================================
   DRAG LEAVE
   ========================================================= */

if (dropZone) {

    dropZone.addEventListener(
        "dragleave",
        function (event) {

            event.preventDefault();

            dropZone.classList.remove(
                "dragging"
            );

        }
    );

}


/* =========================================================
   DROP
   ========================================================= */

if (dropZone) {

    dropZone.addEventListener(
        "drop",
        function (event) {

            event.preventDefault();

            dropZone.classList.remove(
                "dragging"
            );


            const files =
                event.dataTransfer.files;


            if (
                files &&
                files.length > 0
            ) {

                handleFile(
                    files[0]
                );

            }

        }
    );

}


/* =========================================================
   PASTE IMAGE
   ========================================================= */

document.addEventListener(
    "paste",
    function (event) {

        const items =
            event.clipboardData.items;


        if (!items) {

            return;

        }


        for (
            let i = 0;
            i < items.length;
            i++
        ) {

            const item =
                items[i];


            if (
                item.type.startsWith(
                    "image/"
                )
            ) {

                const file =
                    item.getAsFile();


                if (file) {

                    handleFile(
                        file
                    );

                }


                event.preventDefault();

                break;

            }

        }

    }
);


/* =========================================================
   HANDLE IMAGE
   ========================================================= */

function handleFile(file) {

    /* -----------------------------------------------------
       Validate image
       ----------------------------------------------------- */

    if (
        !file.type.startsWith(
            "image/"
        )
    ) {

        showStatus(
            "Please select a valid image.",
            "error"
        );

        return;

    }


    /* -----------------------------------------------------
       Save selected file
       ----------------------------------------------------- */

    selectedFile =
        file;


    /* -----------------------------------------------------
       Create original image preview
       ----------------------------------------------------- */

    const imageURL =
        URL.createObjectURL(
            file
        );


    originalImage.src =
        imageURL;


    /* -----------------------------------------------------
       Show preview
       ----------------------------------------------------- */

    previewSection.classList.add(
        "visible"
    );


    /* -----------------------------------------------------
       Clear previous result
       ----------------------------------------------------- */

    resultImage.removeAttribute(
        "src"
    );


    /* -----------------------------------------------------
       Hide download button
       ----------------------------------------------------- */

    downloadButton.classList.remove(
        "visible"
    );


    /* -----------------------------------------------------
       Hide TRY - ON button
       ----------------------------------------------------- */

    if (tryOnButton) {

        tryOnButton.classList.remove(
            "visible"
        );

    }


    /* -----------------------------------------------------
       Release previous browser result URL
       ----------------------------------------------------- */

    if (resultURL) {

        URL.revokeObjectURL(
            resultURL
        );

        resultURL = null;

    }


    /*
       Clear previous temporary server URL.
    */

    processedClothingURL = null;


    /* -----------------------------------------------------
       Clear status
       ----------------------------------------------------- */

    hideStatus();


    /* =====================================================
       AUTOMATICALLY SCROLL TO PREVIEW SECTION
       ===================================================== */

    setTimeout(
        function () {

            previewSection.scrollIntoView({
                behavior: "smooth",
                block: "start"
            });

        },
        300
    );

}


/* =========================================================
   PROCESS CLOTHING
   ========================================================= */

if (processButton) {

    processButton.addEventListener(
        "click",
        async function () {

            if (!selectedFile) {

                showStatus(
                    "Please select or paste an image first.",
                    "error"
                );

                return;

            }


            processButton.disabled = true;


            showStatus(
                '<span class="spinner"></span>' +
                'Processing clothing...',
                "processing",
                true
            );


            const formData =
                new FormData();


            formData.append(
                "image",
                selectedFile
            );


            try {

                /* ------------------------------------------------
                   Send image to Flask
                   ------------------------------------------------ */

                const response =
                    await fetch(
                        "/process",
                        {
                            method: "POST",
                            body: formData
                        }
                    );


                /* ------------------------------------------------
                   Check response
                   ------------------------------------------------ */

                if (!response.ok) {

                    let errorMessage =
                        "Failed to process image.";


                    try {

                        const errorData =
                            await response.json();


                        if (
                            errorData &&
                            errorData.error
                        ) {

                            errorMessage =
                                errorData.error;

                        }

                    }
                    catch (error) {

                        // Ignore JSON parsing errors.

                    }


                    throw new Error(
                        errorMessage
                    );

                }


                /* ------------------------------------------------
                   Get response JSON
                   ------------------------------------------------ */

                const data =
                    await response.json();


                /* ------------------------------------------------
                   Validate server response
                   ------------------------------------------------ */

                if (
                    !data.success ||
                    !data.url
                ) {

                    throw new Error(
                        data.error ||
                        "Server did not return a processed image."
                    );

                }


                /* ------------------------------------------------
                   Save temporary server URL
                   ------------------------------------------------ */

                processedClothingURL =
                    data.url;


                /* ------------------------------------------------
                   Fetch temporary processed PNG
                   ------------------------------------------------ */

                const imageResponse =
                    await fetch(
                        processedClothingURL
                    );


                if (!imageResponse.ok) {

                    throw new Error(
                        "Could not load processed clothing image."
                    );

                }


                /* ------------------------------------------------
                   Convert response to Blob
                   ------------------------------------------------ */

                const blob =
                    await imageResponse.blob();


                /* ------------------------------------------------
                   Release previous result URL
                   ------------------------------------------------ */

                if (resultURL) {

                    URL.revokeObjectURL(
                        resultURL
                    );

                }


                /* ------------------------------------------------
                   Create temporary browser result URL
                   ------------------------------------------------ */

                resultURL =
                    URL.createObjectURL(
                        blob
                    );


                /* ------------------------------------------------
                   Display result
                   ------------------------------------------------ */

                resultImage.src =
                    resultURL;


                /* ------------------------------------------------
                   Configure download
                   ------------------------------------------------ */

                downloadButton.href =
                    resultURL;


                downloadButton.download =
                    "clothing.png";


                downloadButton.classList.add(
                    "visible"
                );


                /* ------------------------------------------------
                   Show TRY - ON
                   ------------------------------------------------ */

                if (tryOnButton) {

                    tryOnButton.classList.add(
                        "visible"
                    );

                }


                /* ------------------------------------------------
                   Success
                   ------------------------------------------------ */

                showStatus(
                    "Clothing processed successfully!",
                    "success"
                );

            }
            catch (error) {

                console.error(
                    "Processing error:",
                    error
                );


                if (tryOnButton) {

                    tryOnButton.classList.remove(
                        "visible"
                    );

                }


                showStatus(
                    error.message ||
                    "Something went wrong.",
                    "error"
                );

            }
            finally {

                processButton.disabled =
                    false;

            }

        }
    );

}


/* =========================================================
   TRY - ON BUTTON
   ========================================================= */

if (tryOnButton) {

    tryOnButton.addEventListener(
        "click",
        function () {

            if (
                !processedClothingURL
            ) {

                showStatus(
                    "Please process the clothing image first.",
                    "error"
                );

                return;

            }


            openProcessedClothingInTryOn();

        }
    );

}


/* =========================================================
   OPEN PROCESSED CLOTHING IN TRY-ON
   ========================================================= */

function openProcessedClothingInTryOn() {

    if (
        !processedClothingURL
    ) {

        showStatus(
            "Processed clothing is not available.",
            "error"
        );

        return;

    }


    /*
       IMPORTANT:

       Only the SHORT temporary server URL
       is placed in the query string.

       Example:

       /try-on?clothing=/temporary-clothes/abc123

       We DO NOT send the actual image data.

       This prevents HTTP 414 URI Too Long.
    */


    const tryOnURL =
        "/try-on?clothing=" +
        encodeURIComponent(
            processedClothingURL
        );


    const tryOnWindow =
        window.open(
            tryOnURL,
            "_blank"
        );


    if (!tryOnWindow) {

        showStatus(
            "Please allow pop-ups for Fabrix.",
            "error"
        );

    }

}


/* =========================================================
   OPEN DEFAULT CLOTHING IN TRY-ON
   ========================================================= */

function openClothingInTryOn(
    clothingURL
) {

    if (!clothingURL) {

        return;

    }


    /*
       Default clothing files are already
       available from Flask.

       Example:

       /try-on?clothing=/clothes/shirt.png
    */


    const tryOnURL =
        "/try-on?clothing=" +
        encodeURIComponent(
            clothingURL
        );


    const tryOnWindow =
        window.open(
            tryOnURL,
            "_blank"
        );


    if (!tryOnWindow) {

        showStatus(
            "Please allow pop-ups for Fabrix.",
            "error"
        );

    }

}


/* =========================================================
   LOAD CLOTHES
   ========================================================= */

async function loadClothes() {

    try {

        const response =
            await fetch(
                "/clothes"
            );


        if (!response.ok) {

            throw new Error(
                "Could not load clothes."
            );

        }


        const clothes =
            await response.json();


        clothesGrid.innerHTML =
            "";


        if (
            !clothes ||
            clothes.length === 0
        ) {

            clothesGrid.innerHTML = `
                <div class="empty-clothes">
                    No clothing images found.
                </div>
            `;

            return;

        }


        clothes.forEach(
            function (clothing) {

                createClothingCard(
                    clothing
                );

            }
        );

    }
    catch (error) {

        console.error(
            "Clothes loading error:",
            error
        );


        clothesGrid.innerHTML = `
            <div class="empty-clothes">
                Unable to load clothes.
            </div>
        `;

    }

}


/* =========================================================
   CREATE CLOTHING CARD
   ========================================================= */

function createClothingCard(
    clothing
) {

    const card =
        document.createElement(
            "div"
        );


    card.className =
        "clothing-card";


    const imageWrapper =
        document.createElement(
            "div"
        );


    imageWrapper.className =
        "clothing-image";


    const image =
        document.createElement(
            "img"
        );


    image.src =
        clothing.url;


    image.alt =
        "Clothing";


    imageWrapper.appendChild(
        image
    );


    card.appendChild(
        imageWrapper
    );


    /* -----------------------------------------------------
       Select clothing
       ----------------------------------------------------- */

    card.addEventListener(
        "click",
        function () {

            document
                .querySelectorAll(
                    ".clothing-card"
                )
                .forEach(
                    function (item) {

                        item.classList.remove(
                            "selected"
                        );

                    }
                );


            card.classList.add(
                "selected"
            );


            selectedClothing =
                clothing;


            console.log(
                "Selected clothing:",
                clothing
            );


            /*
               Clicking a default clothing image
               immediately opens the live try-on
               page in a new tab.
            */

            openClothingInTryOn(
                clothing.url
            );

        }
    );


    clothesGrid.appendChild(
        card
    );

}


/* =========================================================
   SHOW STATUS
   ========================================================= */

function showStatus(
    message,
    type,
    allowHTML = false
) {

    if (!status) {

        return;

    }


    if (allowHTML) {

        status.innerHTML =
            message;

    }
    else {

        status.textContent =
            message;

    }


    status.className =
        "status visible " +
        type;

}


/* =========================================================
   HIDE STATUS
   ========================================================= */

function hideStatus() {

    if (!status) {

        return;

    }


    status.className =
        "status";


    status.textContent =
        "";

}


/* =========================================================
   CLEANUP BROWSER OBJECT URL
   ========================================================= */

window.addEventListener(
    "beforeunload",
    function () {

        if (resultURL) {

            URL.revokeObjectURL(
                resultURL
            );

            resultURL = null;

        }

    }
);


/* =========================================================
   INITIALIZE
   ========================================================= */

loadClothes();