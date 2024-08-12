/**
 * Main JavaScript file that handles the website's functionality.
 */
import { GUI } from './gui.js';
import { Page } from './page.js';
import { Menu } from './menu.js';
class Website {
  constructor() {
    this.gui = new GUI();
    this.page = new Page(this.gui);
    this.menu = new Menu(this.gui);
  }
  start() {
    const container = document.createElement('div');
    container.id = 'app';
    this.gui.render(container);
    this.page.render(container);
    this.menu.render(container);
    document.body.appendChild(container);
  }
}
const website = new Website();
website.start();