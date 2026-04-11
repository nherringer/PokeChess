type SoundSlot =
  | "piece_move"
  | "attack_hit"
  | "pokeball_shake"
  | "evolution_sting"
  | "win"
  | "loss"
  | "piece_select";

export const soundManager = {
  play: (_slot: SoundSlot) => {
    /* no-op in v1 */
  },
  mute: () => {
    /* no-op in v1 */
  },
  unmute: () => {
    /* no-op in v1 */
  },
};
