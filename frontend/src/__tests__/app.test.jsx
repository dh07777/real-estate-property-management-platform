import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, it, expect } from "vitest";
import { Login } from "../pages/Auth";
import { AuthProvider } from "../auth";
import { ToastProvider, PropertyCard, inr } from "../ui";

const wrap = (ui) => render(<MemoryRouter><ToastProvider><AuthProvider>{ui}</AuthProvider></ToastProvider></MemoryRouter>);

describe("EstateFlow UI", () => {
  it("renders the login form with demo account shortcuts", () => {
    wrap(<Login />);
    expect(screen.getByRole("button", { name: /^sign in$/i })).toBeTruthy();
    expect(screen.getByRole("button", { name: /tenant/i })).toBeTruthy();
  });
  it("formats INR in lakh and crore", () => {
    expect(inr(2500000)).toBe("₹25.00 L");
    expect(inr(12000000)).toBe("₹1.20 Cr");
  });
  it("shows a rental card with monthly price and demo label", () => {
    wrap(<PropertyCard p={{ id: 1, title: "2 BHK Flat", listing_type: "rent", monthly_rent: 30000, locality: "Baner", city: "Pune", bedrooms: 2, bathrooms: 2, area_sqft: 900, status: "available", is_demo: true }} />);
    expect(screen.getByText(/30,000\/mo/)).toBeTruthy();
    expect(screen.getByText(/Demo listing/)).toBeTruthy();
  });
});
