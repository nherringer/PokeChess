"use client";

import { useState, useMemo } from "react";
import { useRouter } from "next/navigation";
import Image from "next/image";
import { Tabs } from "@/components/ui/Tabs";
import { Button } from "@/components/ui/Button";
import { Spinner } from "@/components/ui/Spinner";
import { useFriends } from "@/lib/hooks/useFriends";
import { sendFriendRequest, respondToFriend } from "@/lib/api/friends";
import {
  createInvite,
  respondToInvite,
  cancelInviteAsInviter,
} from "@/lib/api/invites";
import { ApiError } from "@/lib/api/client";
import { useInvites } from "@/lib/hooks/useInvites";
import { dedupeInvitesByPlayerPair } from "@/lib/game/inviteUtils";
import { useAuthStore } from "@/lib/store/authStore";
import type { FriendUser, FriendRequest, InviteOut } from "@/lib/types/api";

type InviteSide = "red" | "blue" | "random";

function FriendRow({
  friend,
  onInvite,
}: {
  friend: FriendUser;
  onInvite: (userId: string, side: InviteSide) => void;
}) {
  const [picking, setPicking] = useState(false);
  const [selectedSide, setSelectedSide] = useState<InviteSide | null>(null);
  const initials = friend.username.slice(0, 2).toUpperCase();

  const handleConfirm = () => {
    if (!selectedSide) return;
    onInvite(friend.user_id, selectedSide);
    setPicking(false);
    setSelectedSide(null);
  };

  const handleCancel = () => {
    setPicking(false);
    setSelectedSide(null);
  };

  const sideOptions: { value: InviteSide; label: string; color: string }[] = [
    { value: "red",    label: "RED",    color: "#d93737" },
    { value: "blue",   label: "BLUE",   color: "#3b5ee5" },
    { value: "random", label: "RANDOM", color: "#666" },
  ];

  return (
    <div className="py-3 border-b border-white/5 last:border-0">
      <div className="flex items-center gap-3">
        <div className="w-10 h-10 rounded-full bg-poke-blue flex items-center justify-center font-bold text-white text-sm shrink-0">
          {initials}
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2">
            <span className="font-bold text-white text-sm">{friend.username}</span>
            <span className="w-2 h-2 rounded-full bg-green-400 shrink-0" title="Online" />
          </div>
        </div>
        {picking ? (
          <button
            onClick={handleCancel}
            className="text-white/40 hover:text-white/70 text-lg leading-none px-1"
            aria-label="Cancel"
          >
            ×
          </button>
        ) : (
          <Button size="sm" variant="secondary" onClick={() => setPicking(true)}>
            Challenge ▶
          </Button>
        )}
      </div>

      {/* Inline side picker — shown when Challenge is clicked */}
      {picking && (
        <div className="mt-3 ml-13 pl-1 flex flex-col gap-2">
          <p className="text-xs text-white/50">Choose your team:</p>
          <div className="flex gap-2">
            {sideOptions.map(({ value, label, color }) => {
              const active = selectedSide === value;
              return (
                <button
                  key={value}
                  onClick={() => setSelectedSide(value)}
                  className="px-3 py-1.5 rounded-lg text-xs font-bold border transition-all"
                  style={{
                    borderColor: color,
                    color: active ? "#fff" : color,
                    backgroundColor: active ? color : "transparent",
                  }}
                >
                  {label}
                </button>
              );
            })}
          </div>
          <Button
            size="sm"
            variant="secondary"
            onClick={handleConfirm}
            disabled={!selectedSide}
          >
            Send invite
          </Button>
        </div>
      )}
    </div>
  );
}

function RequestRow({
  req,
  onAccept,
  onDecline,
}: {
  req: FriendRequest;
  onAccept: () => void;
  onDecline: () => void;
}) {
  return (
    <div className="flex items-center gap-3 py-3 border-b border-white/5 last:border-0">
      <div className="w-10 h-10 rounded-full bg-bg-card flex items-center justify-center font-bold text-white text-sm shrink-0">
        {req.username.slice(0, 2).toUpperCase()}
      </div>
      <span className="flex-1 text-white text-sm">{req.username}</span>
      <div className="flex gap-2">
        <Button size="sm" variant="secondary" onClick={onAccept}>
          Accept
        </Button>
        <Button size="sm" variant="danger" onClick={onDecline}>
          Decline
        </Button>
      </div>
    </div>
  );
}

function IncomingGameInviteRow({
  inv,
  onAccept,
  onDecline,
}: {
  inv: InviteOut;
  onAccept: () => void;
  onDecline: () => void;
}) {
  // The invitee plays the opposite side from the inviter.
  const inviteeSide = inv.inviter_side === "red" ? "blue" : "red";
  const sideColor = inviteeSide === "red" ? "#d93737" : "#3b5ee5";
  const sideLabel = inviteeSide.toUpperCase();

  return (
    <div className="flex items-center gap-3 py-3 border-b border-white/5 last:border-0">
      <div className="w-10 h-10 rounded-full bg-red-team/30 flex items-center justify-center font-bold text-white text-sm shrink-0">
        {inv.other_username.slice(0, 2).toUpperCase()}
      </div>
      <div className="flex-1 min-w-0">
        <p className="text-white text-sm font-bold truncate">{inv.other_username}</p>
        <p className="text-[11px] font-semibold mt-0.5" style={{ color: sideColor }}>
          You play as {sideLabel}
        </p>
      </div>
      <div className="flex gap-2 shrink-0">
        <Button size="sm" variant="secondary" onClick={onAccept}>
          Play
        </Button>
        <Button size="sm" variant="danger" onClick={onDecline}>
          Decline
        </Button>
      </div>
    </div>
  );
}

function OutgoingGameInviteRow({
  inv,
  onCancel,
}: {
  inv: InviteOut;
  onCancel: () => void;
}) {
  return (
    <div className="flex items-center gap-3 py-3 border-b border-white/5 last:border-0">
      <div className="w-10 h-10 rounded-full bg-poke-blue/30 flex items-center justify-center font-bold text-white text-sm shrink-0">
        {inv.other_username.slice(0, 2).toUpperCase()}
      </div>
      <div className="flex-1 min-w-0">
        <p className="text-white text-sm font-bold truncate">{inv.other_username}</p>
        <p className="text-text-muted text-xs">Invite pending</p>
      </div>
      <Button size="sm" variant="ghost" onClick={onCancel}>
        Cancel
      </Button>
    </div>
  );
}

export default function FriendsPage() {
  const router = useRouter();
  const userId = useAuthStore((s) => s.userId);
  const { data, loading, error, unauthenticated, refresh } = useFriends();
  const { data: invites, refresh: refreshInvites, dismissInvite } = useInvites();
  const [activeTab, setActiveTab] = useState(0);
  const [searchQuery, setSearchQuery] = useState("");
  const [searchStatus, setSearchStatus] = useState<string | null>(null);
  const [searchError, setSearchError] = useState<string | null>(null);
  const [sendingReq, setSendingReq] = useState(false);
  const [inviteActionError, setInviteActionError] = useState<string | null>(null);

  const friends = data?.friends ?? [];
  const incoming = data?.incoming ?? [];
  const outgoing = data?.outgoing ?? [];

  const handleSendRequest = async () => {
    if (!searchQuery.trim()) return;
    setSendingReq(true);
    setSearchStatus(null);
    setSearchError(null);
    try {
      const isEmail = searchQuery.includes("@");
      await sendFriendRequest(
        isEmail ? { email: searchQuery.trim() } : { username: searchQuery.trim() }
      );
      setSearchStatus("Request sent!");
      setSearchQuery("");
      refresh();
    } catch (err) {
      setSearchError(err instanceof Error ? err.message : "Failed to send request");
    } finally {
      setSendingReq(false);
    }
  };

  const invitesDeduped = useMemo(
    () => (invites?.length ? dedupeInvitesByPlayerPair(invites) : []),
    [invites]
  );

  /** Someone challenged you to a battle. */
  const incomingGameInvites = useMemo(() => {
    if (!userId) return [];
    return invitesDeduped.filter(
      (i) => String(i.invitee_id) === String(userId)
    );
  }, [invitesDeduped, userId]);

  const outgoingGameInvites = useMemo(() => {
    if (!userId) return [];
    return invitesDeduped.filter(
      (i) => String(i.inviter_id) === String(userId)
    );
  }, [invitesDeduped, userId]);

  const handleInvite = async (userId: string, side: InviteSide) => {
    setInviteActionError(null);
    try {
      const res = await createInvite(userId, side);
      await refreshInvites();
      router.push(
        `/play/lobby?mode=pvp&inviteId=${res.invite_id}&gameId=${res.game_id}`
      );
    } catch (err) {
      if (err instanceof ApiError && err.status === 409) {
        setInviteActionError(err.message);
        return;
      }
      console.error("Invite error:", err);
      setInviteActionError(
        err instanceof Error ? err.message : "Could not send invite"
      );
    }
  };

  const handleGameInviteAccept = async (inv: InviteOut) => {
    setInviteActionError(null);
    try {
      const res = await respondToInvite(inv.id, "accept");
      dismissInvite(inv.id);
      await refreshInvites();
      router.push(`/game?id=${res.game_id}`);
    } catch (err) {
      await refreshInvites();
      setInviteActionError(
        err instanceof Error ? err.message : "Could not accept invite"
      );
    }
  };

  const handleGameInviteDecline = async (inv: InviteOut) => {
    setInviteActionError(null);
    try {
      await respondToInvite(inv.id, "reject");
      dismissInvite(inv.id);
      await refreshInvites();
    } catch (err) {
      await refreshInvites();
      setInviteActionError(
        err instanceof Error ? err.message : "Could not decline invite"
      );
    }
  };

  const handleCancelOutgoingGameInvite = async (inv: InviteOut) => {
    setInviteActionError(null);
    try {
      await cancelInviteAsInviter(inv.id);
      dismissInvite(inv.id);
      await refreshInvites();
    } catch (err) {
      await refreshInvites();
      setInviteActionError(
        err instanceof Error ? err.message : "Could not cancel invite"
      );
    }
  };

  const handleRespondToFriend = async (id: string, action: "accept" | "reject") => {
    try {
      await respondToFriend(id, action);
      refresh();
    } catch (err) {
      console.error("Respond error:", err);
    }
  };

  /** Friend requests only — matches GET /friends (MASTERDOC §5.1); not game invites (GET /game-invites). */
  const friendRequestsBadge = incoming.length + outgoing.length;

  const tabs = [
    { label: "Friends" },
    { label: "Requests", badge: friendRequestsBadge },
  ];

  const hasFriendGraphActivity =
    friends.length > 0 || incoming.length > 0 || outgoing.length > 0;
  const hasPendingGameInvites =
    incomingGameInvites.length > 0 || outgoingGameInvites.length > 0;

  /** Nothing to show: no friends, no friend requests, no battle invites. */
  const showEmptyPikachuState =
    !loading &&
    !error &&
    !hasFriendGraphActivity &&
    !hasPendingGameInvites;

  /** Sub-tabs + lists: show when there is any friend or game-invite activity. */
  const showTabsSection = !loading && !error && (hasFriendGraphActivity || hasPendingGameInvites);

  if (unauthenticated) {
    return (
      <div className="flex flex-col items-center justify-center py-24 text-center gap-4 px-6">
        <span className="text-5xl">🔒</span>
        <h2 className="font-display text-xl font-bold text-white">Log in to see your friends</h2>
        <p className="text-text-muted text-sm">You need an account to add friends and send game invites.</p>
        <a
          href="/login"
          className="mt-2 px-8 py-3 rounded-full font-display font-bold text-white text-base"
          style={{ backgroundColor: "#3B5EE5" }}
        >
          Log In
        </a>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-bg-deep">
      <div className="px-4 pt-6 pb-8 max-w-lg mx-auto">
        <h1 className="font-display text-2xl font-bold text-white mb-4">Friends</h1>

        {inviteActionError && (
          <p className="mb-3 text-xs text-red-team">{inviteActionError}</p>
        )}

        {/* GET /game-invites — separate from GET /friends (MASTERDOC §5.1). */}
        {hasPendingGameInvites && (
          <div className="mb-6 space-y-4">
            {incomingGameInvites.length > 0 && (
              <div className="rounded-xl border border-poke-blue/40 bg-bg-card/80 px-3 py-2">
                <h2 className="text-xs font-bold text-poke-blue uppercase tracking-wide mb-2 px-1">
                  Battle invites
                </h2>
                <p className="text-[11px] text-text-muted mb-2 px-1">
                  Trainers who want to play — accept to start the match.
                </p>
                {incomingGameInvites.map((inv) => (
                  <IncomingGameInviteRow
                    key={inv.id}
                    inv={inv}
                    onAccept={() => handleGameInviteAccept(inv)}
                    onDecline={() => handleGameInviteDecline(inv)}
                  />
                ))}
              </div>
            )}
            {outgoingGameInvites.length > 0 && (
              <div className="rounded-xl border border-white/10 bg-bg-card/50 px-3 py-2">
                <h2 className="text-xs font-bold text-text-muted uppercase tracking-wide mb-2 px-1">
                  Waiting on opponent
                </h2>
                <p className="text-[11px] text-text-muted mb-2 px-1">
                  Battle invites you sent — cancel if you changed your mind.
                </p>
                {outgoingGameInvites.map((inv) => (
                  <OutgoingGameInviteRow
                    key={inv.id}
                    inv={inv}
                    onCancel={() => handleCancelOutgoingGameInvite(inv)}
                  />
                ))}
              </div>
            )}
          </div>
        )}

        {/* Search bar — centered */}
        <div className="mb-6">
          <div className="flex gap-2">
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && handleSendRequest()}
              placeholder="Search by username or email..."
              className="flex-1 bg-bg-card border border-white/10 rounded-xl px-4 py-2.5 text-sm text-white placeholder-white/30 focus:outline-none focus:border-poke-blue transition-colors"
            />
            <Button variant="secondary" size="sm" onClick={handleSendRequest} loading={sendingReq}>
              Add
            </Button>
          </div>
          {searchStatus && <p className="mt-1.5 text-xs text-green-400">{searchStatus}</p>}
          {searchError && <p className="mt-1.5 text-xs text-red-team">{searchError}</p>}
        </div>

        {loading && (
          <div className="flex justify-center py-12">
            <Spinner />
          </div>
        )}

        {error && (
          <div className="text-center py-8 text-red-team text-sm">{error}</div>
        )}

        {/* Empty state with Pikachu */}
        {showEmptyPikachuState && (
          <div className="flex flex-col items-center justify-center py-16 text-center gap-3">
            <Image
              src="https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/25.png"
              alt="Pikachu"
              width={96}
              height={96}
              className="opacity-80"
              unoptimized
            />
            <h2 className="font-display text-xl font-bold text-white">No friends yet!</h2>
            <p className="text-text-muted text-sm">
              Search for a Trainer above to get started!
            </p>
          </div>
        )}

        {/* Tabs: Friends list vs friend requests only (POST/PUT /friends). */}
        {showTabsSection && (
          <>
            <Tabs tabs={tabs} active={activeTab} onChange={setActiveTab} className="mb-4" />

            {activeTab === 0 && (
              <div>
                {friends.length === 0 ? (
                  <p className="text-center text-text-muted text-sm py-8">
                    No friends yet. Add someone using the search bar!
                  </p>
                ) : (
                  friends.map((f) => (
                    <FriendRow key={f.user_id} friend={f} onInvite={handleInvite} />
                  ))
                )}
              </div>
            )}

            {activeTab === 1 && (
              <div>
                {incoming.length > 0 && (
                  <div className="mb-6">
                    <h3 className="text-xs font-bold text-text-muted uppercase tracking-wide mb-2">
                      Incoming
                    </h3>
                    {incoming.map((req) => (
                      <RequestRow
                        key={req.id}
                        req={req}
                        onAccept={() => handleRespondToFriend(req.id, "accept")}
                        onDecline={() => handleRespondToFriend(req.id, "reject")}
                      />
                    ))}
                  </div>
                )}
                {outgoing.length > 0 && (
                  <div>
                    <h3 className="text-xs font-bold text-text-muted uppercase tracking-wide mb-2">
                      Outgoing
                    </h3>
                    {outgoing.map((req) => (
                      <div
                        key={req.id}
                        className="flex items-center gap-3 py-3 border-b border-white/5 last:border-0"
                      >
                        <div className="w-10 h-10 rounded-full bg-bg-card flex items-center justify-center font-bold text-white text-sm shrink-0">
                          {req.username.slice(0, 2).toUpperCase()}
                        </div>
                        <span className="flex-1 text-white/70 text-sm">{req.username}</span>
                        <span className="text-xs text-text-muted">(pending)</span>
                        <Button
                          size="sm"
                          variant="ghost"
                          onClick={() => handleRespondToFriend(req.id, "reject")}
                        >
                          Cancel
                        </Button>
                      </div>
                    ))}
                  </div>
                )}
                {incoming.length === 0 && outgoing.length === 0 && (
                  <p className="text-center text-text-muted text-sm py-8">
                    No pending friend requests.
                  </p>
                )}
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
}
