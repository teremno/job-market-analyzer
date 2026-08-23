const base = process.env.NEXT_PUBLIC_API_BASE_URL || "http://127.0.0.1:8000";
console.log("fetching:", base + "/api/health");
try {
    const res = await fetch(base + "/api/health", {
        signal: AbortSignal.timeout(5000),
        cache: "no-store",
    });
    console.log("status:", res.status);
    console.log("body:", await res.text());
} catch (error) {
    console.log("FETCH FAILED:", error.name, "-", error.message, "-", error.cause?.message ?? "");
}
