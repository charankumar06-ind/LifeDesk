import { Link } from "react-router-dom";
import { Button } from "../components/ui";

export default function NotFound() {
  return (
    <div className="flex min-h-[60vh] flex-col items-start justify-center">
      <div className="label-micro mb-3">404</div>
      <h1 className="serif text-[34px] leading-tight text-bone">This page is not on the desk.</h1>
      <p className="mt-2 max-w-md text-[13px] leading-relaxed text-muted">
        The link may be out of date. Everything in LifeDesk is reachable from the main navigation.
      </p>
      <Link to="/" className="mt-5">
        <Button variant="primary">Back to dashboard</Button>
      </Link>
    </div>
  );
}
