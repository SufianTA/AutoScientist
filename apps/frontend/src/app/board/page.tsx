import { apiGet } from "@/lib/api";

type Post = {
  id: string;
  post_type: string;
  agent_author: string;
  content: Record<string, unknown>;
  created_at: string;
};

export default async function BoardPage() {
  const data = await apiGet<{ posts: Post[] }>("/board/posts");
  return (
    <main className="page">
      <div className="kicker">Research board</div>
      <h1>Hypotheses, critiques, and revisions</h1>
      <div className="grid">
        {data.posts.map((post) => (
          <article className="card" key={post.id}>
            <span className="badge">{post.post_type}</span>
            <h2>{String(post.content.title ?? post.content.critique_type ?? "Board post")}</h2>
            <p className="muted">{post.agent_author} · {new Date(post.created_at).toLocaleString()}</p>
            <pre>{JSON.stringify(post.content, null, 2)}</pre>
          </article>
        ))}
      </div>
    </main>
  );
}

