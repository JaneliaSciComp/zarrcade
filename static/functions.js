// Dark mode functionality
function initTheme() {
    const savedTheme = localStorage.getItem('theme');
    const systemPrefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
    const theme = savedTheme || (systemPrefersDark ? 'dark' : 'light');

    document.documentElement.setAttribute('data-theme', theme);
    const toggle = document.getElementById('theme-toggle');
    if (toggle) {
        toggle.checked = theme === 'dark';
    }
}

function toggleTheme() {
    const currentTheme = document.documentElement.getAttribute('data-theme');
    const newTheme = currentTheme === 'dark' ? 'light' : 'dark';

    document.documentElement.setAttribute('data-theme', newTheme);
    localStorage.setItem('theme', newTheme);
}

// Listen for system theme changes
window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', (e) => {
    if (!localStorage.getItem('theme')) {
        document.documentElement.setAttribute('data-theme', e.matches ? 'dark' : 'light');
        const toggle = document.getElementById('theme-toggle');
        if (toggle) {
            toggle.checked = e.matches;
        }
    }
});

// Initialize theme on page load
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initTheme);
} else {
    initTheme();
}

function showCopied(node) {
    const copied = "Copied!"
    let curr = node.getAttribute("data-tooltip")
    node.setAttribute("data-tooltip", copied)
    if (curr != copied) {
        setTimeout(function() {
            node.setAttribute("data-tooltip", curr)
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