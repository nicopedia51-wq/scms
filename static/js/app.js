// Decision form: require a comment when rejecting, and confirm before sending.
document.addEventListener("DOMContentLoaded", function () {
  var form = document.getElementById("decision-form");
  if (!form) return;
  form.addEventListener("submit", function (e) {
    var choice = form.querySelector('input[name="decision"]:checked');
    var comment = form.querySelector('textarea[name="comment"]');
    if (!choice) { e.preventDefault(); alert("Choose Approve or Reject."); return; }
    if (choice.value === "reject") {
      if (!comment.value.trim()) { e.preventDefault(); alert("Please explain why you are rejecting, so the student knows what to fix."); comment.focus(); return; }
      if (!confirm("Reject this clearance request?")) e.preventDefault();
    }
  });
});
