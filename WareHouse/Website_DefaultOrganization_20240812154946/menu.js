/**
 * File that handles the menu functionality.
 */
class Menu {
  constructor(gui) {
    this.gui = gui;
    this.element = document.createElement('ul');
    this.element.id = 'menu';
    this.element.innerHTML = `
      <li><a href="#">Home</a></li>
      <li><a href="#">About</a></li>
      <li><a href="#">Contact</a></li>
    `;
  }
  render(container) {
    container.appendChild(this.element);
  }
}
export { Menu };