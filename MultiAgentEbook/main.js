const hamburger = document.querySelector(".hamburger-container");
const tabNav = document.querySelector(".tab-nav");
const tabNavList = document.querySelectorAll(".tab-nav li");
const tabList = document.querySelectorAll(".tab-body");
const questions = document.querySelectorAll(".question");
const logoContainer = document.querySelector('.logo-container');
let toggle = false;

hamburger.addEventListener("click", function () {
  const hamburger = document.querySelector(".hamburger");
  const navList = document.querySelector(".nav-list");
  toggle = !toggle;
  let srcHam = "./images/icon-hamburger.svg";
  let srcClose = "./images/icon-close.svg";
  hamburger.src = toggle ? srcClose : srcHam;
  navList.classList.toggle("active");
  logoContainer.classList.toggle('active');
  document.body.style.position = toggle ? 'fixed' : 'static';
});

tabNavList.forEach((item, index, array) => {
  item.addEventListener("click", () => {
    tabNav.querySelector(".active").classList.remove("active");
    item.classList.add("active");

    if (item.classList.contains("one")) {
      tabList[0].classList.add("active");
      tabList[1].classList.remove("active");
    }

    if (item.classList.contains("two")) {
      tabList[1].classList.add("active");
      tabList[0].classList.remove("active");
    }
  });
});

questions.forEach((item) => {
  item.addEventListener("click", () => {
    item.classList.toggle("open");
  });
});