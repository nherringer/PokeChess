// Auth
export interface TokenResponse {
  access_token: string;
  token_type: string;
  user_id: string;
}

export interface PieceOut {
  id: string;
  role: string;
  species: string;
  xp: number;
  evolution_stage: number;
}

export interface UserProfile {
  id: string;
  username: string;
  email: string;
  created_at: string;
  pieces: PieceOut[];
}

// Friends
export interface FriendUser {
  user_id: string;
  username: string;
}

export interface FriendRequest {
  id: string;
  from_user_id: string;
  to_user_id: string;
  username: string;
}

export interface FriendsResponse {
  friends: FriendUser[];
  incoming: FriendRequest[];
  outgoing: FriendRequest[];
}

export interface FriendActionResponse {
  id: string;
  status: string;
}

// Invites
export interface InviteOut {
  id: string;
  from_user_id: string;
  from_username: string;
  game_id: string;
  created_at: string;
}

export interface InviteActionResponse {
  invite_id: string;
  status: string;
  game_id: string;
}

// Game state (JSONB shapes)
export interface ForesightEffect {
  target_row: number;
  target_col: number;
  damage: number;
  resolves_on_turn: number;
}

export interface BoardPieceData {
  id: string | null;
  piece_type: string;
  team: "RED" | "BLUE";
  row: number;
  col: number;
  current_hp: number;
  held_item: string;
  stored_piece: BoardPieceData | null;
}

export interface GameStateData {
  active_player: "RED" | "BLUE";
  turn_number: number;
  has_traded: Record<string, boolean>;
  foresight_used_last_turn: Record<string, boolean>;
  pending_foresight: Record<string, ForesightEffect | null>;
  board: BoardPieceData[];
}

export interface MoveHistoryEntry {
  turn: number;
  player: "RED" | "BLUE";
  action_type: string;
  piece_id: string | null;
  result: Record<string, unknown>;
  from_row?: number;
  from_col?: number;
  to_row?: number;
  to_col?: number;
  target_piece_id?: string | null;
}

// Games
export interface GameSummary {
  id: string;
  status: "pending" | "active" | "complete";
  whose_turn: "red" | "blue" | null;
  turn_number: number;
  is_bot_game: boolean;
  bot_side: "red" | "blue" | null;
  red_player_id: string | null;
  blue_player_id: string | null;
  winner: "red" | "blue" | "draw" | null;
  updated_at: string;
}

export interface GameDetail extends GameSummary {
  end_reason: string | null;
  state: GameStateData | null;
  move_history: MoveHistoryEntry[];
}

export interface GamesListResponse {
  active: GameSummary[];
  completed: GameSummary[];
}

export interface CreateGameRequest {
  bot_id: string;
  player_side: "red" | "blue";
}

// Moves
export interface LegalMoveOut {
  piece_row: number;
  piece_col: number;
  action_type: string;
  target_row: number;
  target_col: number;
  secondary_row: number | null;
  secondary_col: number | null;
  move_slot: number | null;
}

export interface MovePayload extends LegalMoveOut {}
