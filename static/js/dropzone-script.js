var DropzoneExample = function () {
    var DropzoneDemos = function () {
        Dropzone.options.singleFileUpload = {
            paramName: "resumefile",
            maxFiles: 1,
            maxFilesize: 5,
            accept: function(file, done) {
                if (file.type !== "application/pdf") {
                    done("Please upload a pdf files.");
                } else {
                    done();
                }
            }
        };

        // Initialize a timer
        var uploadTimeout;

        // Function to display a message when the upload takes too long
        function displayUploadTimeoutMessage() {
            alert("The upload is taking too long. Please check your internet connection and try again.");
        }

        Dropzone.options.singleFileUpload.init = function() {
            this.on("sending", function(file) {
                var timeout = 30000; // Set a timeout of 30 seconds (adjust as needed)

                // Clear any existing timers
                clearTimeout(uploadTimeout);

                // Set a new timer to display the message if the upload takes too long
                uploadTimeout = setTimeout(displayUploadTimeoutMessage, timeout);
            });

            this.on("success", function(file) {
                // If the upload is successful, clear the timer
                clearTimeout(uploadTimeout);
            });
        };
        
        Dropzone.options.multiFileUpload = {
            paramName: "resumefile",
            maxFiles: 10,
            maxFilesize: 10,
            accept: function(file, done) {
                if (file.type !== "application/pdf") {
                    done("Please upload a pdf files.");
                } else {
                    done();
                }
            }
        };
        Dropzone.options.fileTypeValidation = {
            paramName: "resumefile",
            maxFiles: 10,
            maxFilesize: 10, 
            acceptedFiles: "image/*,application/pdf,.psd",
            accept: function(file, done) {
                if (file.type !== "application/pdf") {
                    done("Please upload a pdf files.");
                } else {
                    done();
                }
            }
        };
    }
    return {
        init: function() {
            DropzoneDemos();
        }
    };
}();
DropzoneExample.init();