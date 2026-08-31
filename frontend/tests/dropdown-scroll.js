import { createApp, h, nextTick, reactive } from 'vue'
import { createI18n } from 'vue-i18n'
import DynamicFormField from '../src/components/DynamicFormField.vue'

const options = ['agent', 'python', 'subgraph', 'passthrough', 'human', 'literal', 'loop_counter', 'loop_timer']
const formData = reactive({ type: 'agent', other: 'agent' })
const changes = []
const field = (name) => ({ name, type: 'str', required: true, enum: options })

createApp({
  render: () => ['type', 'other'].map((name) => h(DynamicFormField, {
    field: field(name),
    formData,
    modalId: 'regression',
    onHandleEnumChange: (changed) => changes.push(changed.name)
  }))
}).use(createI18n({
  legacy: false,
  locale: 'en',
  messages: { en: { dynamic_form_field: { type_to_filter: 'Choose a type' } } }
})).mount('#fixture')

const assert = (condition, message) => {
  if (!condition) throw new Error(message)
}
const settle = async () => {
  await nextTick()
  await new Promise((resolve) => requestAnimationFrame(() => requestAnimationFrame(resolve)))
  await nextTick()
}
const mousedown = (target) => target.dispatchEvent(new MouseEvent('mousedown', { bubbles: true }))
const open = async (name = 'type') => {
  document.getElementById(`regression-${name}`).click()
  await settle()
  const menus = document.querySelectorAll('.custom-select-dropdown')
  const menu = menus[menus.length - 1]
  assert(menu, 'Dropdown did not open')
  return menu
}
const reset = async () => {
  mousedown(document.getElementById('outside'))
  document.getElementById('scroller').scrollTop = 0
  await settle()
  formData.type = 'agent'
  formData.other = 'agent'
  changes.length = 0
}

const tests = [
  ['internal scrolling keeps the menu open', async () => {
    const menu = await open()
    assert(menu.scrollHeight > menu.clientHeight, 'Fixture must overflow')
    menu.scrollTop = menu.scrollHeight
    await settle()
    assert(menu.isConnected, 'Scrolling inside the menu closed it')
    assert(menu.scrollTop > 0, 'Menu did not scroll')
  }],
  ['mousedown on the menu does not count as an outside click', async () => {
    const menu = await open()
    mousedown(menu)
    await settle()
    assert(menu.isConnected, 'Mousedown on the menu closed it')
  }],
  ['mousedown on the menu leaves its default action enabled', async () => {
    const menu = await open()
    const event = new MouseEvent('mousedown', { bubbles: true, cancelable: true })
    menu.dispatchEvent(event)
    await settle()
    assert(!event.defaultPrevented, 'Menu canceled the default scrollbar action')
    assert(menu.isConnected, 'Mousedown on the menu closed it')
  }],
  ...['literal', 'loop_counter', 'loop_timer'].map((value) => [
    `the scrolled ${value} option can be selected`, async () => {
      const menu = await open()
      menu.scrollTop = menu.scrollHeight
      await settle()
      assert(menu.isConnected, 'Menu closed before the option could be selected')
      const option = [...menu.children].find((child) => child.textContent.trim() === value)
      mousedown(option)
      await settle()
      assert(formData.type === value, 'Selection was not saved')
      assert(changes.length === 1 && changes[0] === 'type', 'Selection event was not emitted once')
      assert(!menu.isConnected, 'Selecting an option should close the menu')
    }
  ]),
  ['outside mousedown still closes the menu', async () => {
    const menu = await open()
    mousedown(document.getElementById('outside'))
    await settle()
    assert(!menu.isConnected, 'Outside click left the menu open')
  }],
  ['scrolling the containing form still closes the menu', async () => {
    const menu = await open()
    document.getElementById('scroller').scrollTop = 1
    await settle()
    assert(!menu.isConnected, 'Background scrolling left the menu open')
  }],
  ['window scroll still closes the menu', async () => {
    const menu = await open()
    window.dispatchEvent(new Event('scroll'))
    await settle()
    assert(!menu.isConnected, 'Window scrolling left the menu open')
  }],
  ['only the menu being scrolled stays open', async () => {
    const first = await open()
    const second = await open('other')
    assert(first.isConnected, 'Programmatic opening must leave both menus available')
    second.scrollTop = second.scrollHeight
    await settle()
    assert(!first.isConnected, 'Another menu scrolling should close the first')
    assert(second.isConnected, 'The scrolled menu should stay open')
  }]
]

const results = []
for (const [name, run] of tests) {
  await reset()
  try {
    await run()
    results.push(`PASS ${name}`)
  } catch (error) {
    results.push(`FAIL ${name}: ${error.message}`)
  }
}
await reset()
const output = document.getElementById('results')
output.textContent = results.join('\n')
output.dataset.status = results.some((result) => result.startsWith('FAIL')) ? 'failed' : 'passed'
