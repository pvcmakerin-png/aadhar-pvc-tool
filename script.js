function startPaymentProcess() {
    const fileInput = document.getElementById("pdfInput");
    const passInput = document.getElementById("pdfPassword");

    if (!fileInput || fileInput.files.length === 0) {
        alert("Please select a PDF file first!");
        return; 
    }
    if (passInput && passInput.value.trim() === "") {
        alert("Please enter the PDF Password first.");
        passInput.focus(); 
        return; 
    }

    if (typeof window.processWalletPayment === "function") {
        window.processWalletPayment(1.20, "White Aadhar Generation", function() {
            sendToPythonServer(); 
        });
    } else {
        console.warn("Wallet Function Missing. Proceeding directly...");
        sendToPythonServer(); 
    }
}

async function sendToPythonServer() {
    const fileInput = document.getElementById('pdfInput').files[0];
    const password = document.getElementById('pdfPassword').value;
    const isAutoMobile = document.querySelector('input[name="autoMobile"]:checked').value;

    const btnText = document.getElementById('btnText');
    const spinner = document.getElementById('loadingSpinner');
    const generateBtn = document.getElementById('generateBtn');

    // UI Loading State
    if(btnText) btnText.style.display = 'none';
    if(spinner) spinner.style.display = 'inline-block';
    if(generateBtn) generateBtn.disabled = true;

    const formData = new FormData();
    formData.append("pdf_file", fileInput);
    formData.append("password", password);
    formData.append("autoMobile", isAutoMobile);

    try {
        // 🔥 UPDATE THIS URL WITH YOUR LIVE PYTHON SERVER URL 🔥
        const pythonServerUrl = "https://aadhar-pvc-tool.onrender.com/process_aadhaar"; 
        
        const response = await fetch(pythonServerUrl, {
            method: "POST",
            body: formData
        });

        const data = await response.json();

        if (response.ok) {
            document.getElementById('frontImg').src = "data:image/png;base64," + data.front_image;
            document.getElementById('backImg').src = "data:image/png;base64," + data.back_image;
            
            document.getElementById('downloadFront').href = "data:image/png;base64," + data.front_image;
            document.getElementById('downloadBack').href = "data:image/png;base64," + data.back_image;

            document.getElementById('outputArea').style.display = 'flex';
            triggerConfetti();
        } else {
            alert("Error: " + data.error);
        }
    } catch (error) {
        console.error(error);
        alert("Failed to connect to Python Server! Check if the server is running.");
    } finally {
        if(btnText) btnText.style.display = 'inline';
        if(spinner) spinner.style.display = 'none';
        if(generateBtn) generateBtn.disabled = false;
    }
}

function triggerConfetti() {
    if (typeof confetti !== "function") return;
    var duration = 3 * 1000; 
    var animationEnd = Date.now() + duration;
    var defaults = { startVelocity: 30, spread: 360, ticks: 60, zIndex: 9999 };
    function randomInRange(min, max) { return Math.random() * (max - min) + min; }
    var interval = setInterval(function() {
        var timeLeft = animationEnd - Date.now();
        if (timeLeft <= 0) return clearInterval(interval);
        var particleCount = 50 * (timeLeft / duration);
        confetti(Object.assign({}, defaults, { particleCount, origin: { x: randomInRange(0.1, 0.3), y: Math.random() - 0.2 } }));
        confetti(Object.assign({}, defaults, { particleCount, origin: { x: randomInRange(0.7, 0.9), y: Math.random() - 0.2 } }));
    }, 250);
}
