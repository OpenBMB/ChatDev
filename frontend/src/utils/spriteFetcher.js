/**
 * SpriteFetcher manages sprite image selection.
 * It provides random sprite selection and tracks used sprites to avoid duplicates.
 */
export class SpriteFetcher {
  constructor() {
    // Available character list (1-12)
    this.availableCharacters = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12]
    // Map of characters already bound to node_id
    this.nodeCharacterMap = new Map()
    // Unassigned character pool for random allocation
    this.unassignedCharacters = [...this.availableCharacters]
  }

  /**
   * Get a random sprite image path.
   * @param {string} node_id - Node ID used to bind a character.
   * @param {string} stance - Stance ('D', 'L', 'R', 'U').
   * @param {number} frame - Frame number (1, 2, 3).
   * @returns {string} Image path.
   */
  fetchSprite(node_id = null, stance = 'D', frame = 1) {
    let character

    if (node_id) {
      // Use the bound character if this node already has one.
      if (this.nodeCharacterMap.has(node_id)) {
        character = this.nodeCharacterMap.get(node_id)
      } else {
        // If no character is bound, choose one at random.
        if (this.unassignedCharacters.length === 0) {
          // If all characters are assigned, pick one from the assigned pool.
          character = this.availableCharacters[Math.floor(Math.random() * this.availableCharacters.length)]
        } else {
          // Pick randomly from the unassigned pool.
          const randomIndex = Math.floor(Math.random() * this.unassignedCharacters.length)
          character = this.unassignedCharacters[randomIndex]
          this.unassignedCharacters.splice(randomIndex, 1)
        }

        // Bind the character to the node.
        this.nodeCharacterMap.set(node_id, character)
      }
    } else {
      // If no node_id is specified, select a random character.
      character = this.availableCharacters[Math.floor(Math.random() * this.availableCharacters.length)]
    }

    // Build the sprite path.
    const spritePath = `/sprites/${character}-${stance}-${frame}.png`

    return spritePath
  }

  /**
   * Get current usage status.
   * @returns {Object} Usage status summary.
   */
  getStatus() {
    return {
      totalCharacters: this.availableCharacters.length,
      assignedNodes: this.nodeCharacterMap.size,
      unassignedCount: this.unassignedCharacters.length,
      nodeCharacterMap: Object.fromEntries(this.nodeCharacterMap),
      unassignedCharacters: [...this.unassignedCharacters].sort((a, b) => a - b)
    }
  }

  /**
   * Reset usage state and clear used sprite records.
   */
  reset() {
    this.nodeCharacterMap.clear()
    this.unassignedCharacters = [...this.availableCharacters]
    console.log('Sprite usage state reset')
  }
}

// Create a singleton instance.
export const spriteFetcher = new SpriteFetcher()
