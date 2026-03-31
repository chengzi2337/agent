(function () {
  const STORAGE_KEY = "northwind-hub-state-v1";
  const ITEM = {
    slug: "northwind-canvas-pack",
    name: "Northwind Canvas Pack",
    price: "$23.00"
  };

  function readState() {
    try {
      const parsed = JSON.parse(localStorage.getItem(STORAGE_KEY) || "{}");
      return {
        searchStatus: parsed.searchStatus || "",
        detailVisited: Boolean(parsed.detailVisited),
        cartItems: Array.isArray(parsed.cartItems) ? parsed.cartItems : [],
        lastPage: parsed.lastPage || "index"
      };
    } catch (_error) {
      return {
        searchStatus: "",
        detailVisited: false,
        cartItems: [],
        lastPage: "index"
      };
    }
  }

  function writeState(nextState) {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(nextState));
  }

  function withState(mutator) {
    const nextState = readState();
    mutator(nextState);
    writeState(nextState);
    return nextState;
  }

  function setText(selector, value) {
    const node = document.querySelector(selector);
    if (node) {
      node.textContent = value;
    }
  }

  function markPage(name) {
    withState((state) => {
      state.lastPage = name;
    });
  }

  function renderNav() {
    const count = readState().cartItems.length;
    setText("#nav-cart-count", String(count));
  }

  function renderIndex() {
    const state = readState();
    const hasItem = state.cartItems.includes(ITEM.name);
    setText(
      "#hub-status",
      hasItem
        ? "Cart is carrying Northwind Canvas Pack. Final hub return is available."
        : "Use Catalog Search for live work. Avoid Operations Console and Archive Mirror unless the task explicitly forces them."
    );

    const reset = document.querySelector("#reset-state");
    if (reset) {
      reset.addEventListener("click", function () {
        localStorage.removeItem(STORAGE_KEY);
        window.location.reload();
      });
    }
  }

  function renderCatalog() {
    const input = document.querySelector("#catalog-query");
    const trigger = document.querySelector("#run-search");
    const results = document.querySelector("#search-results");
    const status = document.querySelector("#search-status");
    const params = new URLSearchParams(window.location.search);
    const seeded = params.get("q") || "";
    const saved = readState().searchStatus;

    function showResult(query) {
      const normalized = String(query || "").trim().toLowerCase();
      results.innerHTML = "";
      if (normalized.includes("northwind") || normalized.includes("canvas")) {
        status.textContent = "Search locked on Northwind Canvas Pack.";
        const link = document.createElement("a");
        link.href = "detail.html?item=" + ITEM.slug;
        link.className = "button-link";
        link.textContent = "Open Northwind Canvas Pack";
        results.appendChild(link);
        withState((state) => {
          state.searchStatus = status.textContent;
        });
      } else {
        status.textContent = "No live item matched that query.";
        withState((state) => {
          state.searchStatus = "";
        });
      }
    }

    if (input) {
      input.value = seeded || "";
    }
    if (!seeded && saved) {
      status.textContent = saved;
    }
    if (trigger && input) {
      trigger.addEventListener("click", function () {
        showResult(input.value);
      });
    }
    if (seeded) {
      showResult(seeded);
    }
  }

  function renderDetail() {
    setText("#product-title", ITEM.name);
    setText("#product-price", ITEM.price);
    const add = document.querySelector("#add-to-cart");
    const status = document.querySelector("#detail-status");
    const state = readState();
    if (state.detailVisited) {
      status.textContent = ITEM.name + " detail already reviewed.";
    }

    withState((nextState) => {
      nextState.detailVisited = true;
    });

    if (add) {
      add.addEventListener("click", function () {
        const nextState = withState((draft) => {
          draft.detailVisited = true;
          if (!draft.cartItems.includes(ITEM.name)) {
            draft.cartItems.push(ITEM.name);
          }
        });
        status.textContent = ITEM.name + " added to cart.";
        renderNav();
        setText("#cart-preview", nextState.cartItems.join("\n"));
      });
    }
    setText("#cart-preview", state.cartItems.join("\n") || "Cart preview is empty.");
  }

  function renderCart() {
    const items = readState().cartItems;
    setText("#cart-items", items.length ? items.join("\n") : "Cart is currently empty.");
    setText(
      "#cart-status",
      items.includes(ITEM.name)
        ? "Cart ready with Northwind Canvas Pack."
        : "Cart does not yet contain the target item."
    );
  }

  function buildObservation() {
    const page = document.body.getAttribute("data-page") || "page";
    const state = readState();
    return [
      "Northwind Hub page: " + page,
      state.searchStatus ? "Search memory: " + state.searchStatus : "",
      state.detailVisited ? "Detail page has been visited." : "",
      state.cartItems.length ? "Cart: " + state.cartItems.join(", ") : "Cart is empty."
    ]
      .filter(Boolean)
      .join("\n");
  }

  window.__CER_GET_STATE = function () {
    const state = readState();
    return {
      state_signature: JSON.stringify({
        page: document.body.getAttribute("data-page") || "page",
        title: document.title,
        searchStatus: state.searchStatus,
        detailVisited: state.detailVisited,
        cartItems: state.cartItems
      }),
      constraint_compliant: true,
      observation_text: buildObservation()
    };
  };

  window.__CER_FIXTURE_READY = false;

  document.addEventListener("DOMContentLoaded", function () {
    const page = document.body.getAttribute("data-page") || "index";
    markPage(page);
    renderNav();

    if (page === "index") {
      renderIndex();
    } else if (page === "catalog") {
      renderCatalog();
    } else if (page === "detail") {
      renderDetail();
    } else if (page === "cart") {
      renderCart();
    }

    window.__CER_FIXTURE_READY = true;
  });
})();
