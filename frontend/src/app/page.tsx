import { redirect } from "next/navigation";

// Root "/" → chuyển thẳng đến trang login
export default function RootPage() {
  redirect("/login");
}
