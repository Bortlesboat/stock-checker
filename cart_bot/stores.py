STORES = {
    "Target": {
        "login_url": "https://www.target.com/account",
        "add_to_cart_xpath": "//button[@data-test='shipItButton' or @data-test='addToCartButton' or contains(text(), 'Add to cart') or contains(text(), 'Ship it')]",
        "cart_url": "https://www.target.com/cart",
        "checkout_direct": "https://www.target.com/checkout",
        # Check page for error/OOS states BEFORE trusting the ATC button
        "js_page_ok": """
            var t = document.body.innerText.toLowerCase();
            if (/sold out|out of stock|currently unavailable|isn't available|not available|temporarily out/i.test(t)) return false;
            if (/something went wrong|error occurred|page not found|access denied/i.test(t)) return false;
            return true;
        """,
        "js_find_atc": """
            var t = document.body.innerText.toLowerCase();
            if (/sold out|out of stock|currently unavailable|isn't available|temporarily out/.test(t)) return null;
            if (/something went wrong|error occurred|page not found/.test(t)) return null;
            var btn = document.querySelector('[data-test="shipItButton"], [data-test="addToCartButton"]');
            if (btn && !btn.disabled) return btn;
            var all = [...document.querySelectorAll('button')];
            return all.find(b =>
                /add to cart|ship it/i.test(b.textContent) && !b.disabled
                && !/sold out|unavailable|out of stock/i.test(b.textContent)
            ) || null;
        """,
        "js_click_atc": """
            var t = document.body.innerText.toLowerCase();
            if (/sold out|out of stock|currently unavailable|isn't available|temporarily out/.test(t)) return false;
            if (/something went wrong|error occurred|page not found/.test(t)) return false;
            var btn = document.querySelector('[data-test="shipItButton"], [data-test="addToCartButton"]');
            if (!btn || btn.disabled) {
                btn = [...document.querySelectorAll('button')].find(b =>
                    /add to cart|ship it/i.test(b.textContent) && !b.disabled
                    && !/sold out|unavailable|out of stock/i.test(b.textContent));
            }
            if (btn) { btn.click(); return true; }
            return false;
        """,
        # Get the cart badge count (number next to cart icon). Returns int.
        "js_cart_count": """
            var el = document.querySelector('[data-test="@web/CartLink"] span, [data-test="cart-count"], [aria-label*="cart"] span');
            if (el) { var n = parseInt(el.textContent); return isNaN(n) ? 0 : n; }
            // Fallback: look for any small number near cart icon area
            var links = document.querySelectorAll('a[href*="/cart"]');
            for (var i = 0; i < links.length; i++) {
                var spans = links[i].querySelectorAll('span');
                for (var j = 0; j < spans.length; j++) {
                    var n = parseInt(spans[j].textContent);
                    if (!isNaN(n) && n >= 0 && n < 100) return n;
                }
            }
            return -1;
        """,
        # Check for ATC confirmation modal/toast on same page
        "js_verify_atc": """
            var body = document.body.innerText.toLowerCase();
            if (/added to cart|item added|added!/.test(body)) return 'confirmed';
            var btns = document.querySelectorAll('button');
            for (var i = 0; i < btns.length; i++) {
                if (/^added$/i.test(btns[i].textContent.trim())) return 'confirmed';
            }
            return 'unconfirmed';
        """,
    },
    "Walmart": {
        "login_url": "https://www.walmart.com/account/login",
        "add_to_cart_xpath": "//button[contains(@data-testid, 'add-to-cart') or @class='add-to-cart-button' or contains(text(), 'Add to cart')]",
        "cart_url": "https://www.walmart.com/cart",
        "checkout_direct": "https://www.walmart.com/checkout",
        "js_page_ok": """
            var t = document.body.innerText.toLowerCase();
            if (/sold out|out of stock|currently unavailable|not available/i.test(t)) return false;
            if (/something went wrong|error occurred|page not found/i.test(t)) return false;
            return true;
        """,
        "js_find_atc": """
            var t = document.body.innerText.toLowerCase();
            if (/sold out|out of stock|currently unavailable|not available/.test(t)) return null;
            if (/something went wrong|error occurred|page not found/.test(t)) return null;
            var btn = document.querySelector('[data-testid*="add-to-cart"], .add-to-cart-button');
            if (btn && !btn.disabled) return btn;
            return [...document.querySelectorAll('button')].find(b =>
                /add to cart/i.test(b.textContent) && !b.disabled
                && !/sold out|unavailable|out of stock/i.test(b.textContent)
            ) || null;
        """,
        "js_click_atc": """
            var t = document.body.innerText.toLowerCase();
            if (/sold out|out of stock|currently unavailable|not available/.test(t)) return false;
            if (/something went wrong|error occurred|page not found/.test(t)) return false;
            var btn = document.querySelector('[data-testid*="add-to-cart"], .add-to-cart-button');
            if (!btn || btn.disabled) {
                btn = [...document.querySelectorAll('button')].find(b =>
                    /add to cart/i.test(b.textContent) && !b.disabled
                    && !/sold out|unavailable|out of stock/i.test(b.textContent));
            }
            if (btn) { btn.click(); return true; }
            return false;
        """,
        "js_cart_count": """
            var el = document.querySelector('.cart-count, [data-testid="cart-count"], [aria-label*="Cart"] span');
            if (el) { var n = parseInt(el.textContent); return isNaN(n) ? 0 : n; }
            var links = document.querySelectorAll('a[href*="/cart"]');
            for (var i = 0; i < links.length; i++) {
                var spans = links[i].querySelectorAll('span');
                for (var j = 0; j < spans.length; j++) {
                    var n = parseInt(spans[j].textContent);
                    if (!isNaN(n) && n >= 0 && n < 100) return n;
                }
            }
            return -1;
        """,
        "js_verify_atc": """
            var body = document.body.innerText.toLowerCase();
            if (/added to cart|item added/.test(body)) return 'confirmed';
            return 'unconfirmed';
        """,
    },
}
