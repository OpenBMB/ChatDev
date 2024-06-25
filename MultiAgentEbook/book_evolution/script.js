document.addEventListener("DOMContentLoaded", function() {
    
    const csvFilePath = './book_evolution/data.csv';

    
    function loadCSV(filePath) {
        return fetch(filePath)
            .then(response => response.text())
            .then(text => Papa.parse(text, { header: true }).data);
    }

    
    function createFlipBook(pages) {
        const container = document.getElementById('flip_book_container');
        const numPages = pages.length;

        let flipBookHTML = '';
        let style = document.createElement('style');
        let css = '';

        
        flipBookHTML += `<input type="checkbox" id="cover_checkbox">\n`;
        for (let i = 0; i < numPages - 1; i++) {
            flipBookHTML += `<input type="checkbox" id="page${i + 1}_checkbox">\n`;
        }

        flipBookHTML += `<div id="flip_book">\n`;

        flipBookHTML += `<div class="front_cover">
        <label for="cover_checkbox" id="cover">
            <img src="./images/3.png" alt="Book Cover" class="cover_image">
        </label>
        </div>`

        
        for (let i = 0; i < numPages - 1; i++) {
            console.log(i)
            const page = pages[i];
            const pageIndex = i + 1;

            flipBookHTML += `
            <div class="page" id="page${pageIndex}">
                <div class="front_page">
                    <label for="page${pageIndex}_checkbox"></label>
                    <img class="back_content" src="${page.image_path}" alt="Back content">
                </div>
                <div class="back_page">
                    <label for="page${pageIndex}_checkbox"></label>
                    <img class="edge_shading" src="./images/back_page_edge_shading.png" alt="Back page edge shading">
                    <div class="text_content">
                        <h1>${page.title}</h1>
                        <p class="author">${page.author}</p>
                        <p class="author">${page.affiliation}</p>
                        <div class="text_content_summary"><p class="summary">${page.summary}</p></div>
                    </div>
                </div>
            </div>\n`;

            
            css += `
            #page${pageIndex} {
                z-index: ${numPages - i};
            }

            #page${pageIndex}_checkbox:checked~#flip_book #page${pageIndex} {
                transform: rotateY(-180deg);
                z-index: ${i + 1};
            }\n`;
        }

        flipBookHTML += `<div class="back_cover">
        <img src="./images/3a.png" alt="Back Cover" class="cover_image">
        </div>`;

        
        container.innerHTML = flipBookHTML;

        
        style.innerHTML = css;
        document.head.appendChild(style);

        
        const md = window.markdownit();
        const summaryElements = document.querySelectorAll('.summary');
        summaryElements.forEach(el => {
            el.innerHTML = md.render(el.textContent);
        });
    }

    
    loadCSV(csvFilePath).then(pages => {
        createFlipBook(pages);
    });
});
