import React from "react"

function UserReply({ message }) {
  return (
    <p className="font-['Inter:Regular',sans-serif] text-[14px] text-white leading-[1.35] m-0">
      {message}
    </p>
  )
}

export default UserReply