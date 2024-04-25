function showCopied(node) {
    const copied = "Copied!"
    let tooltip = node.querySelector(".tooltiptext")
    let curr = tooltip.textContent
    tooltip.textContent = copied
    if (curr != copied) {
        setTimeout(function() {
            tooltip.textContent = curr
        }, 1000)
    }
}

// Clipboard when the clipboard API is not available (like when using insecure HTTP)
// From https://stackoverflow.com/questions/400212/how-do-i-copy-to-the-clipboard-in-javascript/30810322#30810322
function fallbackCopyTextToClipboard(node, text) {
    var textArea = document.createElement("textarea");
    textArea.value = text;

    // Avoid scrolling to bottom
    textArea.style.top = "0";
    textArea.style.left = "0";
    textArea.style.position = "fixed";

    document.body.appendChild(textArea);
    textArea.focus();
    textArea.select();

    try {
        if (document.execCommand('copy')) {
            showCopied(node);
        }
        else {
            console.log('Fallback clipboard copy failed');
        }
    } catch (err) {}
    
    document.body.removeChild(textArea);
  };
  
async function copyTextToClipboard(node, text) {
    try {
        if (!navigator.clipboard) {
            fallbackCopyTextToClipboard(node, text);
        }
        else {
            await navigator.clipboard.writeText(text).then(function() {
                showCopied(node);
            }, function(err) {
                console.error('Async clipboard copy failed: ', err);
            });
        }
    } catch (err) {
        console.error('Clipboard copy failed: ', err);
    }
}