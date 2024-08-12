/**
 * File that handles the page functionality.
 */
class Page {
  constructor(gui) {
    this.gui = gui;
    this.element = document.createElement('div');
    this.element.id = 'page';
    this.element.innerHTML = `
      <h2>This is a page</h2>
    `;
  }
  render(container) {
    container.appendChild(this.element);
  }
}
export { Page };