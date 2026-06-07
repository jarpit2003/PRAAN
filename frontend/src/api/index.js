const BASE_URL = "https://y353ks4bsq.us-east-1.awsapprunner.com";

export async function getStats() {
  try {
    const res = await fetch(`${BASE_URL}/stats`);
    return await res.json();
  } catch {
    return null;
  }
}

export async function getCritical() {
  try {
    const res = await fetch(`${BASE_URL}/critical`);
    return await res.json();
  } catch {
    return null;
  }
}

export async function getActivity() {
  try {
    const res = await fetch(`${BASE_URL}/activity`);
    return await res.json();
  } catch {
    return null;
  }
}

export async function escalateRequest(id) {
  try {
    const res = await fetch(`${BASE_URL}/requests/${id}/escalate`, {
      method: "POST",
    });
    return await res.json();
  } catch {
    return null;
  }
}

export async function contactBloodBank(id) {
  try {
    const res = await fetch(`${BASE_URL}/requests/${id}/contact-blood-bank`, {
      method: "POST",
    });
    const data = await res.json();
    if (!res.ok) return { sent: false, error: data?.detail || "Server error" };
    return data;
  } catch (e) {
    return { sent: false, error: e.message };
  }
}
