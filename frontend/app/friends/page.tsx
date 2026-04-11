"use client";

import React, { useState } from "react";
import { useRouter } from "next/navigation";
import { PageShell } from "@/components/ui/PageShell";
import { Tabs } from "@/components/ui/Tabs";
import { Button } from "@/components/ui/Button";
import { Spinner } from "@/components/ui/Spinner";
import { useFriends } from "@/lib/hooks/useFriends";
import { sendFriendRequest, respondToFriend } from "@/lib/api/friends";
import { createInvite } from "@/lib/api/invites";
import type { FriendUser, FriendRequest } from "@/lib/types/api";

function FriendRow({
  friend,
  onInvite,
}: {
  friend: FriendUser;
  onInvite: (userId: string) => void;
}) {
  const initials = friend.username.slice(0, 2).toUpperCase();
  return (
    <div className="flex items-center gap-3 py-3 border-b border-white/5 last:border-0">
      {/* Avatar */}
      <div className="w-10 h-10 rounded-full bg-blue-team flex items-center justify-center font-bold text-white text-sm shrink-0">
        {initials}
      </div>
      {/* Name + presence */}
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2">
          <span className="font-bold text-white text-sm">{friend.username}</span>
          <span className="w-2 h-2 rounded-full bg-green-400 shrink-0" title="Online" />
        </div>
      </div>
      <Button size="sm" variant="secondary" onClick={() => onInvite(friend.user_id)}>
        Invite ▶
      </Button>
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

export default function FriendsPage() {
  const router = useRouter();
  const { data, loading, error, refresh } = useFriends();
  const [activeTab, setActiveTab] = useState(0);
  const [searchQuery, setSearchQuery] = useState("");
  const [searchStatus, setSearchStatus] = useState<string | null>(null);
  const [searchError, setSearchError] = useState<string | null>(null);
  const [sendingReq, setSendingReq] = useState(false);

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

  const handleInvite = async (userId: string) => {
    try {
      const res = await createInvite(userId);
      router.push(`/play/lobby?mode=pvp&inviteId=${res.invite_id}`);
    } catch (err) {
      console.error("Invite error:", err);
    }
  };

  const handleRespondToFriend = async (
    id: string,
    action: "accept" | "reject"
  ) => {
    try {
      await respondToFriend(id, action);
      refresh();
    } catch (err) {
      console.error("Respond error:", err);
    }
  };

  const tabs = [
    { label: "Friends" },
    { label: "Requests", badge: incoming.length },
  ];

  const hasNoFriends =
    !loading && friends.length === 0 && incoming.length === 0 && outgoing.length === 0;

  return (
    <PageShell title="Friends">
      <div className="px-4 pt-4 pb-8 max-w-lg mx-auto">
        {/* Search bar */}
        <div className="mb-4">
          <div className="flex gap-2">
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && handleSendRequest()}
              placeholder="Search by username or email..."
              className="flex-1 bg-bg-card border border-white/10 rounded-xl px-4 py-2.5 text-sm text-white placeholder-white/30 focus:outline-none focus:border-blue-team transition-colors"
            />
            <Button
              variant="secondary"
              size="sm"
              onClick={handleSendRequest}
              loading={sendingReq}
            >
              Add
            </Button>
          </div>
          {searchStatus && (
            <p className="mt-1.5 text-xs text-green-400">{searchStatus}</p>
          )}
          {searchError && (
            <p className="mt-1.5 text-xs text-red-400">{searchError}</p>
          )}
        </div>

        {/* Loading */}
        {loading && (
          <div className="flex justify-center py-12">
            <Spinner />
          </div>
        )}

        {/* Error */}
        {error && (
          <div className="text-center py-8 text-red-400 text-sm">{error}</div>
        )}

        {/* Empty state */}
        {hasNoFriends && !loading && !error && (
          <div className="flex flex-col items-center justify-center py-16 text-center gap-3">
            <span className="text-6xl">👋</span>
            <h2 className="font-display text-xl font-bold text-white">No friends yet!</h2>
            <p className="text-white/50 text-sm">
              Add someone to play PokeChess with!
            </p>
          </div>
        )}

        {/* Tabs */}
        {!loading && !hasNoFriends && (
          <>
            <Tabs tabs={tabs} active={activeTab} onChange={setActiveTab} className="mb-4" />

            {activeTab === 0 && (
              <div>
                {friends.length === 0 ? (
                  <p className="text-center text-white/40 text-sm py-8">
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
                    <h3 className="text-xs font-bold text-white/50 uppercase tracking-wide mb-2">
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
                    <h3 className="text-xs font-bold text-white/50 uppercase tracking-wide mb-2">
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
                        <span className="flex-1 text-white/70 text-sm">
                          {req.username}
                        </span>
                        <span className="text-xs text-white/30">(pending)</span>
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
                  <p className="text-center text-white/40 text-sm py-8">
                    No pending requests.
                  </p>
                )}
              </div>
            )}
          </>
        )}
      </div>
    </PageShell>
  );
}
