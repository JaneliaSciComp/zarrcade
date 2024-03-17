async function copyTextToClipboard(node, text) {
    try {
        await navigator.clipboard.writeText(text);
        const copied = "Copied!"
        let tooltip = node.querySelector(".tooltiptext")
        let curr = tooltip.textContent
        tooltip.textContent = copied
        if (curr != copied) {
            setTimeout(function() {
                tooltip.textContent = curr
            }, 1000)
        }
    } catch (err) {
        console.error('Failed to copy text: ', err);
    }
}