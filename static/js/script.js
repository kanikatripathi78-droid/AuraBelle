// ===============================
// AURABELLE FINAL SCRIPT.JS
// ===============================


// 🔍 SEARCH FUNCTION
function searchProduct() {
    filterProducts();
}


// 🎯 FILTER FUNCTION (PRICE BASED)
function filterProduct() {
    filterProducts();
}

function filterProducts() {
    const grid = document.getElementById("product-grid");
    if (!grid) return;

    const searchValue = (document.getElementById("search")?.value || "").trim().toLowerCase();
    const priceFilter = document.getElementById("filter")?.value || "all";
    const sortValue = document.getElementById("sort")?.value || "default";
    const cards = Array.from(grid.querySelectorAll(".card"));

    cards.sort((a, b) => {
        const nameA = a.dataset.name || "";
        const nameB = b.dataset.name || "";
        const priceA = Number(a.dataset.price) || 0;
        const priceB = Number(b.dataset.price) || 0;

        if (sortValue === "name") return nameA.localeCompare(nameB);
        if (sortValue === "price-low") return priceA - priceB;
        if (sortValue === "price-high") return priceB - priceA;
        return 0;
    });

    let visibleCount = 0;

    cards.forEach(card => {
        const name = card.dataset.name || card.innerText.toLowerCase();
        const price = Number(card.dataset.price) || 0;
        const matchesSearch = name.includes(searchValue);
        const matchesPrice =
            priceFilter === "all" ||
            (priceFilter === "low" && price < 500) ||
            (priceFilter === "mid" && price >= 500 && price < 1000) ||
            (priceFilter === "high" && price >= 1000);
        const isVisible = matchesSearch && matchesPrice;

        card.style.display = isVisible ? "" : "none";
        if (isVisible) visibleCount += 1;
        grid.appendChild(card);
    });

    const resultsCount = document.getElementById("results-count");
    const emptyResults = document.getElementById("empty-results");

    if (resultsCount) resultsCount.innerText = visibleCount;
    if (emptyResults) emptyResults.style.display = visibleCount === 0 ? "block" : "none";
}

function resetProductFilters() {
    const search = document.getElementById("search");
    const filter = document.getElementById("filter");
    const sort = document.getElementById("sort");

    if (search) search.value = "";
    if (filter) filter.value = "all";
    if (sort) sort.value = "default";

    filterProducts();
}

function filterOrders() {
    const cards = document.querySelectorAll(".order-card");
    if (cards.length === 0) return;

    const searchValue = (document.getElementById("order-search")?.value || "").trim().toLowerCase();
    const statusValue = document.getElementById("order-status-filter")?.value || "all";
    let visibleCount = 0;

    cards.forEach(card => {
        const searchableText = (card.dataset.search || card.innerText).toLowerCase();
        const status = card.dataset.status || "";
        const matchesSearch = searchableText.includes(searchValue);
        const matchesStatus = statusValue === "all" || status === statusValue;
        const isVisible = matchesSearch && matchesStatus;

        card.style.display = isVisible ? "" : "none";
        if (isVisible) visibleCount += 1;
    });

    const count = document.getElementById("order-count");
    const emptyMessage = document.getElementById("empty-filtered-orders");

    if (count) count.innerText = visibleCount;
    if (emptyMessage) emptyMessage.style.display = visibleCount === 0 ? "block" : "none";
}


// ⭐ STAR RATING SYSTEM
function rateProduct(value) {
    const msg = document.getElementById("rating-msg");
    if (msg) {
        msg.innerText = "You rated this product " + value + " ⭐";
    }

    // Highlight stars
    const stars = document.querySelectorAll(".star");
    stars.forEach((star, index) => {
        if (index < value) {
            star.style.color = "gold";
        } else {
            star.style.color = "gray";
        }
    });
}


// 🌙 DARK MODE TOGGLE (with localStorage)
function toggleDark() {
    document.body.classList.toggle("dark");

    if (document.body.classList.contains("dark")) {
        localStorage.setItem("theme", "dark");
    } else {
        localStorage.setItem("theme", "light");
    }
}

function setupThemeToggle() {
    const navRight = document.querySelector("nav .right");
    if (!navRight || document.getElementById("theme-toggle")) return;

    const button = document.createElement("button");
    button.id = "theme-toggle";
    button.type = "button";
    button.className = "theme-toggle";
    button.innerText = document.body.classList.contains("dark") ? "Light" : "Dark";
    button.onclick = () => {
        toggleDark();
        button.innerText = document.body.classList.contains("dark") ? "Light" : "Dark";
    };
    navRight.appendChild(button);
}


// 🔄 LOAD SAVED THEME
function loadTheme() {
    const theme = localStorage.getItem("theme");

    if (theme === "dark") {
        document.body.classList.add("dark");
    }
}


// ✨ FADE-IN ANIMATION
function applyFadeIn() {
    const elements = document.querySelectorAll(".fade-in");

    elements.forEach((el, index) => {
        el.style.opacity = 0;
        el.style.transform = "translateY(20px)";

        setTimeout(() => {
            el.style.transition = "all 0.5s ease";
            el.style.opacity = 1;
            el.style.transform = "translateY(0)";
        }, index * 120);
    });
}


// 🛒 ADD TO CART FEEDBACK
function addedToCart() {
    showToast("Item added to cart 🛒");
}

function updateCartBadges(count) {
    document.querySelectorAll(".badge").forEach(badge => {
        badge.innerText = count;
    });
}

function updateWishlistBadges(count) {
    document.querySelectorAll(".wishlist-badge").forEach(badge => {
        badge.innerText = count;
    });
}

function setupLiveCartCount() {
    document.querySelectorAll('a[href^="/add_to_cart/"]').forEach(link => {
        link.addEventListener("click", async event => {
            event.preventDefault();

            try {
                const response = await fetch(link.href, {
                    headers: {
                        "X-Requested-With": "XMLHttpRequest"
                    }
                });

                const data = await response.json();

                if (data.redirect) {
                    window.location.href = data.redirect;
                    return;
                }

                if (!response.ok || !data.success) {
                    window.location.href = link.href;
                    return;
                }

                updateCartBadges(data.cart_count);
                addedToCart();
            } catch (error) {
                window.location.href = link.href;
            }
        });
    });
}


// 🔔 TOAST NOTIFICATION (BETTER THAN ALERT)
function setupWishlistButtons() {
    document.querySelectorAll('a[href^="/add_to_wishlist/"]').forEach(link => {
        link.addEventListener("click", async event => {
            event.preventDefault();

            try {
                const response = await fetch(link.href, {
                    headers: {
                        "X-Requested-With": "XMLHttpRequest"
                    }
                });
                const data = await response.json();

                if (data.redirect) {
                    window.location.href = data.redirect;
                    return;
                }

                if (!response.ok || !data.success) {
                    window.location.href = link.href;
                    return;
                }

                link.classList.add("saved");
                link.innerText = "Saved to Wishlist";
                if (typeof data.wishlist_count !== "undefined") {
                    updateWishlistBadges(data.wishlist_count);
                }
                showToast("Saved to wishlist");
            } catch (error) {
                window.location.href = link.href;
            }
        });
    });
}

function setupProductRatings() {
    document.querySelectorAll('form[action^="/rate_product/"]').forEach(form => {
        form.addEventListener("submit", async event => {
            event.preventDefault();

            const submitter = event.submitter;
            if (!submitter) return;

            const formData = new FormData(form);
            formData.set("rating", submitter.value);

            try {
                const response = await fetch(form.action, {
                    method: "POST",
                    body: formData,
                    headers: {
                        "X-Requested-With": "XMLHttpRequest"
                    }
                });
                const data = await response.json();

                if (data.redirect) {
                    window.location.href = data.redirect;
                    return;
                }

                if (!response.ok || !data.success) {
                    form.submit();
                    return;
                }

                form.querySelectorAll(".stars button").forEach(button => {
                    button.classList.toggle("active", Number(button.value) <= data.user_rating);
                });

                const text = form.querySelector(".rating-text");
                if (text) {
                    const label = data.rating_count === 1 ? "rating" : "ratings";
                    text.innerText = `${data.average_rating} / 5 from ${data.rating_count} ${label}`;
                }

                showToast("Rating saved");
            } catch (error) {
                form.submit();
            }
        });
    });
}

function setupPaymentOptions() {
    document.querySelectorAll(".payment-option").forEach(option => {
        const input = option.querySelector("input[type='radio']");
        if (!input) return;

        option.classList.toggle("selected", input.checked);
        option.addEventListener("click", () => {
            input.checked = true;
            document.querySelectorAll(".payment-option").forEach(item => {
                item.classList.remove("selected");
            });
            option.classList.add("selected");
        });
    });
}

function showToast(message) {
    let toast = document.createElement("div");
    toast.innerText = message;

    toast.style.position = "fixed";
    toast.style.bottom = "20px";
    toast.style.right = "20px";
    toast.style.background = "#b497d6";
    toast.style.color = "white";
    toast.style.padding = "12px 20px";
    toast.style.borderRadius = "8px";
    toast.style.boxShadow = "0 5px 15px rgba(0,0,0,0.2)";
    toast.style.zIndex = "1000";

    document.body.appendChild(toast);

    setTimeout(() => {
        toast.remove();
    }, 2000);
}


// 🔼 SCROLL TO TOP BUTTON
function createScrollTop() {
    const btn = document.createElement("button");
    btn.innerText = "↑";

    btn.style.position = "fixed";
    btn.style.bottom = "20px";
    btn.style.left = "20px";
    btn.style.padding = "10px";
    btn.style.border = "none";
    btn.style.background = "#b497d6";
    btn.style.color = "white";
    btn.style.borderRadius = "50%";
    btn.style.cursor = "pointer";

    btn.onclick = () => {
        window.scrollTo({ top: 0, behavior: "smooth" });
    };

    document.body.appendChild(btn);
}


// ===============================
// 🚀 INIT ON PAGE LOAD
// ===============================
window.onload = function () {
    loadTheme();
    setupThemeToggle();
    applyFadeIn();
    filterProducts();
    filterOrders();
    setupLiveCartCount();
    setupWishlistButtons();
    setupProductRatings();
    setupPaymentOptions();
    createScrollTop();
};
