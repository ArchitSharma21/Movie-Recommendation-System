function clearAutocompleteSuggestions() {
    document.querySelectorAll("#autoComplete_list, #food_list, .autoComplete_list").forEach(element => {
        element.innerHTML = "";
        element.style.display = "none";
    });
}

window.clearAutocompleteSuggestions = clearAutocompleteSuggestions;

window.showAutocompleteSuggestions = function() {
    document.querySelectorAll("#autoComplete_list, #food_list, .autoComplete_list").forEach(element => {
        element.style.display = "";
    });
};

new autoComplete({
    data: {                              // Data src [Array, Function, Async] | (REQUIRED)
      src: films,
    },
    selector: "#autoComplete",           // Input field selector              | (Optional)
    threshold: 2,                        // Min. Chars length to start Engine | (Optional)
    debounce: 100,                       // Post duration for engine to start | (Optional)
    searchEngine: "strict",              // Search Engine type/mode           | (Optional)
    resultsList: {                       // Rendered results list object      | (Optional)
        render: true,
        container: source => {
            source.setAttribute("id", "food_list");
        },
        destination: document.querySelector("#autoComplete"),
        position: "afterend",
        element: "ul"
    },
    maxResults: 5,                         // Max. number of rendered results | (Optional)
    highlight: true,                       // Highlight matching results      | (Optional)
    resultItem: {                          // Rendered result item            | (Optional)
        content: (data, source) => {
            source.innerHTML = data.match;
        },
        element: "li"
    },
    noResults: () => {                     // Action script on noResults      | (Optional)
        const list = document.querySelector("#autoComplete_list");
        if (!list || list.querySelector(".no_result")) {
            return;
        }
        const result = document.createElement("li");
        result.setAttribute("class", "no_result");
        result.setAttribute("tabindex", "1");
        result.innerHTML = "No Results";
        list.appendChild(result);
    },
    onSelection: feedback => {             // Action script onSelection event | (Optional)
        const input = document.getElementById('autoComplete');
        input.value = feedback.selection.value;
        input.dispatchEvent(new Event("input", {bubbles: true}));
        clearAutocompleteSuggestions();
    }
});
