"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";

import {
  addComment,
  ago,
  getPost,
  MAX_COMMENT_BODY,
  toggleCommentLike,
  togglePostLike,
  type Comment,
  type PostDetail,
} from "../../../lib/social";

export default function PostClient({ id }: { id: string }) {
  const [post, setPost] = useState<PostDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);

  const load = useCallback(async () => {
    const result = await getPost(id);
    if (result.ok && result.data) {
      setPost(result.data);
      setError(null);
    } else {
      setError(result.detail ?? "This post could not be loaded.");
    }
    setLoading(false);
  }, [id]);

  useEffect(() => {
    void load();
  }, [load]);

  if (loading) {
    return (
      <main>
        <section className="page-head">
          <p className="kicker">bestmodel.run / post</p>
        </section>
        <div className="skel" aria-hidden="true">
          <div className="skel-row" />
        </div>
      </main>
    );
  }

  if (!post) {
    return (
      <main>
        <section className="page-head">
          <p className="kicker">bestmodel.run / post</p>
        </section>
        <p className="banner" data-k="bad" role="status">
          {error ?? "This post could not be loaded."}
        </p>
        <div className="actions">
          <Link className="btn primary" href="/console">
            back to the console
          </Link>
        </div>
      </main>
    );
  }

  return (
    <main>
      <section className="post-head">
        <div className="claim-top">
          <Link className="claim-who" href={post.author_handle ? `/profile/${post.author_handle}` : "/console"}>
            {post.author_handle ? `@${post.author_handle}` : "member"}
          </Link>
          <span className="post-kind">{post.kind}</span>
          <span className="claim-age">{ago(post.created_at) ?? ""}</span>
        </div>
        <p className="post-body">{post.body}</p>
        <PostAttachments post={post} />
      </section>

      <PostActions post={post} onChanged={load} />

      <section className="post-thread">
        <h2 className="post-thread-h">
          {post.comments.length} {post.comments.length === 1 ? "answer" : "answers"}
        </h2>
        <CommentForm postId={post.id} onPosted={load} />
        {post.comments.length === 0 ? (
          <p className="post-note">
            Nobody answered yet. A question without an answer is still worth asking.
          </p>
        ) : (
          <ul className="post-comments">
            {post.comments.map((comment) => (
              <CommentRow key={comment.id} comment={comment} onChanged={load} />
            ))}
          </ul>
        )}
        {message && (
          <p className="form-status" role="status">
            {message}
          </p>
        )}
      </section>
    </main>
  );
}

function PostAttachments({ post }: { post: PostDetail }) {
  const links: Array<{ href: string; label: string }> = [];
  if (post.claim_id) links.push({ href: `/claim/${post.claim_id}`, label: "the claim it is about" });
  if (post.rig_slug) links.push({ href: `/claims?rig=${post.rig_slug}`, label: `rig ${post.rig_slug}` });
  if (post.model_release_id) {
    links.push({ href: `/m/${post.model_release_id}`, label: post.model_release_id });
  }
  if (links.length === 0) return null;
  return (
    <p className="post-attachments">
      {links.map((link, index) => (
        <span key={link.href}>
          {index > 0 ? " · " : ""}
          <Link href={link.href}>{link.label}</Link>
        </span>
      ))}
    </p>
  );
}

function PostActions({ post, onChanged }: { post: PostDetail; onChanged: () => Promise<void> }) {
  const [liked, setLiked] = useState(post.liked_by_viewer);
  const [count, setCount] = useState(post.like_count);
  const [error, setError] = useState<string | null>(null);

  async function like() {
    const result = await togglePostLike(post.id);
    if (!result.ok || !result.data) {
      setError(result.detail ?? "The like could not be recorded.");
      return;
    }
    setLiked(result.data.liked);
    setCount(result.data.like_count);
    setError(null);
    await onChanged();
  }

  return (
    <section className="post-actions">
      <button className={liked ? "btn on" : "btn"} type="button" onClick={() => void like()}>
        {liked ? "Liked" : "Like"} · {count}
      </button>
      <Link className="btn" href="/console">
        write a post
      </Link>
      {error && (
        <p className="help err" role="alert">
          {error}
        </p>
      )}
    </section>
  );
}

function CommentForm({ postId, onPosted }: { postId: string; onPosted: () => Promise<void> }) {
  const [body, setBody] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function submit() {
    const text = body.trim();
    if (!text) {
      setError("Write something first.");
      return;
    }
    setBusy(true);
    const result = await addComment(postId, text);
    setBusy(false);
    if (!result.ok) {
      setError(result.detail ?? "The comment could not be sent.");
      return;
    }
    setBody("");
    setError(null);
    await onPosted();
  }

  return (
    <div className="post-form">
      <div className="field">
        <label htmlFor="comment-body">answer</label>
        <textarea
          id="comment-body"
          value={body}
          maxLength={MAX_COMMENT_BODY}
          onChange={(event) => setBody(event.target.value)}
          placeholder="What do you know about this?"
        />
      </div>
      <div className="desk-actions">
        <button className="btn primary" type="button" disabled={busy} onClick={() => void submit()}>
          {busy ? "sending…" : "Answer"}
        </button>
        {error && (
          <p className="help err" role="alert">
            {error}
          </p>
        )}
      </div>
    </div>
  );
}

function CommentRow({ comment, onChanged }: { comment: Comment; onChanged: () => Promise<void> }) {
  const [liked, setLiked] = useState(comment.liked_by_viewer);
  const [count, setCount] = useState(comment.like_count);

  async function like() {
    const result = await toggleCommentLike(comment.id);
    if (!result.ok || !result.data) return;
    setLiked(result.data.liked);
    setCount(result.data.like_count);
    await onChanged();
  }

  return (
    <li className={comment.parent_id ? "reply" : ""}>
      <div className="claim-top">
        <Link className="claim-who" href={comment.author_handle ? `/profile/${comment.author_handle}` : "/console"}>
          {comment.author_handle ? `@${comment.author_handle}` : "member"}
        </Link>
        <span className="claim-age">{ago(comment.created_at) ?? ""}</span>
      </div>
      <p className="post-body post-comment-body">{comment.body}</p>
      <button className="btn" type="button" onClick={() => void like()}>
        {liked ? "Liked" : "Like"} · {count}
      </button>
    </li>
  );
}
