"""Blog blueprint: public pages + admin CRUD API + RSS feed."""

import re
from datetime import datetime, timezone

from flask import (
    Blueprint, render_template, jsonify, abort,
    request as flask_request, Response,
)
from flask_login import login_required, current_user

from ..extensions import db
from ..models.blog import BlogPost

blog_bp = Blueprint("blog", __name__)


def _slugify(text):
    """Convert text to URL-safe slug."""
    text = text.lower().strip()
    text = re.sub(r"[^\w\s-]", "", text)
    return re.sub(r"[-\s]+", "-", text).strip("-")[:200]


# ── Public Pages ──────────────────────────────────────────────


@blog_bp.route("/blog")
def blog_index():
    """List published blog posts."""
    page = flask_request.args.get("page", 1, type=int)
    per_page = 12
    q = (BlogPost.query
         .filter_by(published=True)
         .order_by(BlogPost.created_at.desc()))
    pagination = q.paginate(
        page=page, per_page=per_page, error_out=False,
    )
    return render_template(
        "blog/index.html",
        posts=pagination.items,
        pagination=pagination,
    )


@blog_bp.route("/blog/<slug>")
def blog_post(slug):
    """Display a single blog post."""
    post = BlogPost.query.filter_by(
        slug=slug, published=True,
    ).first_or_404()
    return render_template("blog/post.html", post=post)


@blog_bp.route("/blog/feed.xml")
def blog_rss():
    """RSS 2.0 feed of published posts."""
    posts = (BlogPost.query
             .filter_by(published=True)
             .order_by(BlogPost.created_at.desc())
             .limit(20)
             .all())
    xml = _build_rss(posts)
    return Response(xml, mimetype="application/rss+xml")


def _build_rss(posts):
    items = ""
    for p in posts:
        pub = p.created_at.strftime(
            "%a, %d %b %Y %H:%M:%S +0000"
        )
        items += f"""<item>
  <title>{_xml_esc(p.title)}</title>
  <link>https://nickelanddime.io/blog/{p.slug}</link>
  <description>{_xml_esc(p.excerpt)}</description>
  <pubDate>{pub}</pubDate>
  <guid>https://nickelanddime.io/blog/{p.slug}</guid>
</item>
"""
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
<channel>
  <title>Nickel&amp;Dime Blog</title>
  <link>https://nickelanddime.io/blog</link>
  <description>Macro investing, portfolio strategy, and \
personal finance insights.</description>
  <language>en-us</language>
  {items}
</channel>
</rss>"""


def _xml_esc(text):
    """Escape XML special characters."""
    return (text
            .replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace('"', "&quot;"))


# ── Admin API ─────────────────────────────────────────────────


def _require_admin():
    if not current_user.is_authenticated:
        abort(401)
    if not getattr(current_user, "is_admin", False):
        abort(403)


@blog_bp.route("/api/blog/posts", methods=["GET"])
@login_required
def admin_list_posts():
    """List all posts (admin)."""
    _require_admin()
    posts = (BlogPost.query
             .order_by(BlogPost.created_at.desc())
             .all())
    return jsonify({"posts": [
        _post_dict(p) for p in posts
    ]})


@blog_bp.route("/api/blog/posts", methods=["POST"])
@login_required
def admin_create_post():
    """Create a new blog post (admin)."""
    _require_admin()
    data = flask_request.get_json(silent=True) or {}
    title = (data.get("title") or "").strip()
    if not title:
        return jsonify({"error": "Title required"}), 400

    slug = _slugify(data.get("slug") or title)
    if BlogPost.query.filter_by(slug=slug).first():
        return jsonify({"error": "Slug already taken"}), 400

    post = BlogPost(
        slug=slug,
        title=title,
        excerpt=(data.get("excerpt") or "")[:500],
        body=data.get("body") or "",
        author_id=current_user.id,
        published=bool(data.get("published")),
        meta_description=(
            data.get("meta_description") or ""
        )[:300],
        og_image=data.get("og_image") or "",
    )
    db.session.add(post)
    db.session.commit()
    return jsonify(_post_dict(post)), 201


@blog_bp.route(
    "/api/blog/posts/<int:post_id>", methods=["PUT"]
)
@login_required
def admin_update_post(post_id):
    """Update a blog post (admin)."""
    _require_admin()
    post = BlogPost.query.get_or_404(post_id)
    data = flask_request.get_json(silent=True) or {}

    if "title" in data:
        post.title = data["title"]
    if "slug" in data:
        new_slug = _slugify(data["slug"])
        existing = BlogPost.query.filter_by(
            slug=new_slug).first()
        if existing and existing.id != post.id:
            return jsonify(
                {"error": "Slug already taken"}
            ), 400
        post.slug = new_slug
    if "excerpt" in data:
        post.excerpt = data["excerpt"][:500]
    if "body" in data:
        post.body = data["body"]
    if "published" in data:
        post.published = bool(data["published"])
    if "meta_description" in data:
        post.meta_description = (
            data["meta_description"][:300]
        )
    if "og_image" in data:
        post.og_image = data["og_image"]

    post.updated_at = datetime.now(timezone.utc)
    db.session.commit()
    return jsonify(_post_dict(post))


@blog_bp.route(
    "/api/blog/posts/<int:post_id>", methods=["DELETE"]
)
@login_required
def admin_delete_post(post_id):
    """Delete a blog post (admin)."""
    _require_admin()
    post = BlogPost.query.get_or_404(post_id)
    db.session.delete(post)
    db.session.commit()
    return jsonify({"success": True})


def _post_dict(post):
    return {
        "id": post.id,
        "slug": post.slug,
        "title": post.title,
        "excerpt": post.excerpt,
        "body": post.body,
        "published": post.published,
        "meta_description": post.meta_description,
        "og_image": post.og_image,
        "created_at": (
            post.created_at.isoformat()
            if post.created_at else None
        ),
        "updated_at": (
            post.updated_at.isoformat()
            if post.updated_at else None
        ),
    }
